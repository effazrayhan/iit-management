import base64
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Literal

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

load_dotenv(Path(__file__).parents[2] / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]
STUDENT_EMAIL_PATTERN = os.getenv(
    "STUDENT_EMAIL_PATTERN",
    r"^bsse(?P<batch>\d{2})(?P<roll>\d{2})@iit\.du\.ac\.bd$",
)
STAFF_EMAIL_DOMAIN = os.getenv("STAFF_EMAIL_DOMAIN", "iit.du.ac.bd")
SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "").strip().lower()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    otp_digest: Mapped[str | None] = mapped_column(String(64))
    otp_purpose: Mapped[str | None] = mapped_column(String(16))
    otp_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_attempts: Mapped[int | None]


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    program: Mapped[str] = mapped_column(String(20))
    batch: Mapped[str] = mapped_column(String(2))
    roll: Mapped[str] = mapped_column(String(2))
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"))
    phone: Mapped[str | None] = mapped_column(String(30))
    hall_id: Mapped[int | None] = mapped_column(ForeignKey("halls.id"))
    hometown_district: Mapped[str | None] = mapped_column(String(100))
    current_address: Mapped[str | None] = mapped_column(Text)
    blood_group: Mapped[str | None] = mapped_column(String(3))
    last_blood_donation: Mapped[date | None] = mapped_column(Date)
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False)


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(255))


class AcademicSession(Base):
    __tablename__ = "academic_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("program_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(100))
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class Semester(Base):
    __tablename__ = "semesters"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    credits: Mapped[float] = mapped_column(Float)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))


class Hall(Base):
    __tablename__ = "halls"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class CRPosition(Base):
    __tablename__ = "cr_positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    title: Mapped[str] = mapped_column(String(100))
    seats: Mapped[int] = mapped_column(default=1)


class CRElection(Base):
    __tablename__ = "cr_elections"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("cr_positions.id"))
    title: Mapped[str] = mapped_column(String(255))
    nomination_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    nomination_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    voting_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    voting_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class CRCandidate(Base):
    __tablename__ = "cr_candidates"
    __table_args__ = (UniqueConstraint("election_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    election_id: Mapped[int] = mapped_column(ForeignKey("cr_elections.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.user_id"))
    manifesto: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="PENDING")


class ElectionParticipation(Base):
    __tablename__ = "election_participation"
    __table_args__ = (UniqueConstraint("election_id", "voter_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    election_id: Mapped[int] = mapped_column(ForeignKey("cr_elections.id"))
    voter_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CRBallot(Base):
    __tablename__ = "cr_ballots"

    id: Mapped[int] = mapped_column(primary_key=True)
    election_id: Mapped[int] = mapped_column(ForeignKey("cr_elections.id"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("cr_candidates.id"))


class CRAppointment(Base):
    __tablename__ = "cr_appointments"
    __table_args__ = (UniqueConstraint("election_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    election_id: Mapped[int] = mapped_column(ForeignKey("cr_elections.id"))
    position_id: Mapped[int] = mapped_column(ForeignKey("cr_positions.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.user_id"))
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class Classroom(Base):
    __tablename__ = "classrooms"
    __table_args__ = (UniqueConstraint("course_id", "batch_id", "teacher_id", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"))
    section: Mapped[str] = mapped_column(String(20), default="A")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class ClassroomEnrollment(Base):
    __tablename__ = "classroom_enrollments"
    __table_args__ = (UniqueConstraint("classroom_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.user_id"))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class ClassSession(Base):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"))
    session_date: Mapped[date] = mapped_column(Date)
    starts_at: Mapped[time] = mapped_column(Time)
    ends_at: Mapped[time] = mapped_column(Time)
    topic: Mapped[str] = mapped_column(String(255), default="")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("class_session_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    class_session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.user_id"))
    status: Mapped[str] = mapped_column(String(20))


class AttendanceAudit(Base):
    __tablename__ = "attendance_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance_records.id"))
    old_status: Mapped[str] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    submitter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text)
    confidential: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="SUBMITTED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("classroom_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.user_id"))
    clarity: Mapped[int]
    organization: Mapped[int]
    fairness: Mapped[int]
    regularity: Mapped[int]
    interaction: Mapped[int]
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Base.metadata.create_all(engine)
if engine.dialect.name == "postgresql":
    with engine.begin() as connection:
        for column in (
            "password_hash VARCHAR(255)",
            "otp_digest VARCHAR(64)",
            "otp_purpose VARCHAR(16)",
            "otp_expires TIMESTAMPTZ",
            "otp_sent_at TIMESTAMPTZ",
            "otp_attempts INTEGER",
        ):
            connection.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column}"))
        for column in (
            "batch_id INTEGER",
            "phone VARCHAR(30)",
            "hall_id INTEGER",
            "hometown_district VARCHAR(100)",
            "current_address TEXT",
            "blood_group VARCHAR(3)",
            "last_blood_donation DATE",
            "profile_completed BOOLEAN DEFAULT FALSE",
        ):
            connection.execute(text(f"ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS {column}"))

app = FastAPI(title="IIT Management API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Signup(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class Signin(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)


class EmailRequest(BaseModel):
    email: str = Field(max_length=255)


class PasswordReset(EmailRequest):
    otp: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=8, max_length=128)


class OtpRequest(EmailRequest):
    otp: str = Field(pattern=r"^\d{6}$")


class TeacherDecision(BaseModel):
    action: Literal["APPROVE", "REJECT", "MAKE_ADMIN"]


class AcademicSetup(BaseModel):
    program_code: str = Field(min_length=1, max_length=20)
    program_name: str = Field(min_length=1, max_length=255)
    academic_session: str = Field(min_length=1, max_length=20)
    batch_code: str = Field(min_length=1, max_length=10)
    batch_name: str = Field(min_length=1, max_length=100)
    semester_number: int = Field(ge=1, le=20)
    semester_name: str = Field(min_length=1, max_length=100)
    course_code: str = Field(min_length=1, max_length=30)
    course_name: str = Field(min_length=1, max_length=255)
    credits: float = Field(ge=0.5, le=10)
    hall_name: str | None = Field(default=None, max_length=255)


class StudentProfileUpdate(BaseModel):
    phone: str = Field(min_length=3, max_length=30)
    hall_id: int | None = None
    hometown_district: str | None = Field(default=None, max_length=100)
    current_address: str = Field(min_length=3, max_length=1000)
    blood_group: Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] | None = None
    last_blood_donation: date | None = None


class CRPositionCreate(BaseModel):
    batch_id: int
    title: str = Field(min_length=1, max_length=100)
    seats: int = Field(default=1, ge=1, le=10)


class ElectionCreate(BaseModel):
    position_id: int
    title: str = Field(min_length=1, max_length=255)
    nomination_start: datetime
    nomination_end: datetime
    voting_start: datetime
    voting_end: datetime


class NominationCreate(BaseModel):
    manifesto: str = Field(default="", max_length=2000)


class CandidateDecision(BaseModel):
    action: Literal["APPROVE", "REJECT"]


class VoteCreate(BaseModel):
    candidate_id: int


class ClassroomCreate(BaseModel):
    course_id: int
    batch_id: int
    semester_id: int
    session_id: int
    section: str = Field(default="A", min_length=1, max_length=20)
    teacher_id: int | None = None


class ClassSessionCreate(BaseModel):
    session_date: date
    starts_at: time
    ends_at: time
    topic: str = Field(default="", max_length=255)


class AttendanceItem(BaseModel):
    student_id: int
    status: Literal["PRESENT", "ABSENT", "LATE", "EXCUSED"]


class AttendanceUpdate(BaseModel):
    records: list[AttendanceItem] = Field(min_length=1)


class ComplaintCreate(BaseModel):
    category: Literal[
        "ACADEMIC", "CLASSROOM", "LAB", "FACILITIES", "TEACHER", "ADMINISTRATION", "HARASSMENT_SAFETY", "OTHER"
    ]
    subject: str = Field(min_length=3, max_length=255)
    details: str = Field(min_length=10, max_length=5000)
    confidential: bool = True


class ComplaintDecision(BaseModel):
    status: Literal["ACKNOWLEDGED", "UNDER_REVIEW", "ASSIGNED", "ACTION_TAKEN", "RESOLVED"]


class FeedbackCreate(BaseModel):
    clarity: int = Field(ge=1, le=5)
    organization: int = Field(ge=1, le=5)
    fairness: int = Field(ge=1, le=5)
    regularity: int = Field(ge=1, le=5)
    interaction: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


def classify_email(email: str) -> tuple[str, str, dict[str, str] | None]:
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+", email):
        raise ValueError("Enter a valid email address")
    match = re.fullmatch(STUDENT_EMAIL_PATTERN, email)
    if match:
        return "STUDENT", "ACTIVE", {
            "program": "BSSE",
            "batch": match.group("batch"),
            "roll": match.group("roll"),
        }
    if email.endswith(f"@{STAFF_EMAIL_DOMAIN}"):
        return "TEACHER", "PENDING", None
    raise ValueError("Use an IIT email address")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        salt, expected = (base64.b64decode(part) for part in encoded.split("$", 1))
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (AttributeError, ValueError):
        return False


def otp_hash(email: str, otp: str, purpose: str = "RESET") -> str:
    return hmac.new(JWT_SECRET.encode(), f"{purpose}:{email}:{otp}".encode(), hashlib.sha256).hexdigest()


def prepare_otp(user: User, email: str, purpose: str, now: datetime) -> str:
    otp = f"{secrets.randbelow(1_000_000):06d}"
    user.otp_digest = otp_hash(email, otp, purpose)
    user.otp_purpose = purpose
    user.otp_expires = now + timedelta(minutes=10)
    user.otp_sent_at = now
    user.otp_attempts = 5
    return otp


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def send_otp(email: str, otp: str, purpose: str) -> None:
    message = EmailMessage()
    action = "verify your email" if purpose == "VERIFY" else "reset your password"
    message["Subject"] = f"IIT Management: {action}"
    message["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
    message["To"] = email
    message.set_content(f"Your code to {action} is {otp}. It expires in 10 minutes.")
    with smtplib.SMTP_SSL(
        os.getenv("SMTP_HOST", "smtp.gmail.com"),
        int(os.getenv("SMTP_PORT", "465")),
        context=ssl.create_default_context(),
    ) as smtp:
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def make_token(user: User) -> str:
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def current_user(authorization: str = Header()) -> User:
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError
        user_id = int(jwt.decode(token, JWT_SECRET, algorithms=["HS256"])["sub"])
    except (ValueError, KeyError, jwt.PyJWTError):
        raise HTTPException(401, "Invalid session")
    with Session(engine) as db:
        user = db.get(User, user_id)
        if not user or user.status != "ACTIVE":
            raise HTTPException(403, "Account is not active")
        if user.role == "SUPER_ADMIN" and user.email != SUPER_ADMIN_EMAIL:
            raise HTTPException(403, "Super admin is no longer configured")
        db.expunge(user)
        return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role not in {"SUPER_ADMIN", "DEPARTMENT_ADMIN"}:
        raise HTTPException(403, "Admin access required")
    return user


def student_user(user: User = Depends(current_user)) -> User:
    if user.role != "STUDENT":
        raise HTTPException(403, "Student access required")
    return user


def teacher_or_admin(user: User = Depends(current_user)) -> User:
    if user.role not in {"TEACHER", "SUPER_ADMIN", "DEPARTMENT_ADMIN"}:
        raise HTTPException(403, "Teacher or admin access required")
    return user


def get_student(db: Session, user_id: int) -> StudentProfile:
    profile = db.get(StudentProfile, user_id)
    if not profile:
        raise HTTPException(404, "Student profile not found")
    return profile


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/signup", status_code=201)
def signup(body: Signup):
    try:
        email = body.email.strip().lower()
        if email == SUPER_ADMIN_EMAIL:
            if not re.fullmatch(r"[^@\s]+@[^@\s]+", email):
                raise ValueError("Enter a valid email address")
            role, student = "SUPER_ADMIN", None
        else:
            role, _, student = classify_email(email)
        if not body.name.strip():
            raise ValueError("Enter your name")
    except ValueError as error:
        raise HTTPException(400, str(error))

    with Session(engine) as db:
        user = User(
            email=email,
            name=body.name.strip(),
            password_hash=hash_password(body.password),
            role=role,
            status="UNVERIFIED",
        )
        db.add(user)
        try:
            db.flush()
            if student:
                batch = db.scalar(
                    select(Batch)
                    .join(Program)
                    .where(Program.code == student["program"], Batch.code == student["batch"])
                )
                db.add(StudentProfile(user_id=user.id, batch_id=batch.id if batch else None, **student))
                if batch:
                    for classroom_id in db.scalars(
                        select(Classroom.id).where(
                            Classroom.batch_id == batch.id, Classroom.status == "ACTIVE"
                        )
                    ):
                        db.add(ClassroomEnrollment(classroom_id=classroom_id, student_id=user.id))
            otp = prepare_otp(user, email, "VERIFY", datetime.now(timezone.utc))
            send_otp(email, otp, "VERIFY")
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "An account already exists for this email")
        except (KeyError, OSError, smtplib.SMTPException):
            raise HTTPException(503, "Email service is unavailable")
        db.refresh(user)

        return {
            "token": None,
            "user": {"email": user.email, "name": user.name, "role": user.role},
            "status": user.status,
        }


@app.post("/api/auth/resend-verification")
def resend_verification(body: EmailRequest):
    email = body.email.strip().lower()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        now = datetime.now(timezone.utc)
        if not user or user.status != "UNVERIFIED" or (user.otp_purpose == "VERIFY" and user.otp_sent_at and now - aware(user.otp_sent_at) < timedelta(minutes=1)):
            return {"message": "If verification is pending, a new code has been sent."}
        otp = prepare_otp(user, email, "VERIFY", now)
        try:
            send_otp(email, otp, "VERIFY")
            db.commit()
        except (KeyError, OSError, smtplib.SMTPException):
            raise HTTPException(503, "Email service is unavailable")
    return {"message": "If verification is pending, a new code has been sent."}


@app.post("/api/auth/verify-email")
def verify_email(body: OtpRequest):
    email = body.email.strip().lower()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        now = datetime.now(timezone.utc)
        valid = bool(
            user
            and user.status == "UNVERIFIED"
            and user.otp_purpose == "VERIFY"
            and user.otp_digest
            and user.otp_expires
            and aware(user.otp_expires) > now
            and (user.otp_attempts or 0) > 0
            and hmac.compare_digest(user.otp_digest, otp_hash(email, body.otp, "VERIFY"))
        )
        if not valid:
            if user and (user.otp_attempts or 0) > 0:
                user.otp_attempts -= 1
                db.commit()
            raise HTTPException(400, "Invalid or expired verification code")
        user.status = "ACTIVE" if user.role in {"STUDENT", "SUPER_ADMIN"} else "PENDING"
        user.otp_digest = None
        user.otp_purpose = None
        user.otp_expires = None
        user.otp_attempts = 0
        db.commit()
        db.refresh(user)
        return {
            "token": make_token(user) if user.status == "ACTIVE" else None,
            "user": {"email": user.email, "name": user.name, "role": user.role},
            "status": user.status,
        }


@app.post("/api/auth/signin")
def signin(body: Signin):
    email = body.email.strip().lower()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Invalid email or password")
        if user.status == "UNVERIFIED":
            raise HTTPException(403, "Email is not verified")
        if email == SUPER_ADMIN_EMAIL:
            user.role = "SUPER_ADMIN"
            user.status = "ACTIVE"
            db.commit()
            db.refresh(user)
        if user.status != "ACTIVE":
            raise HTTPException(403, "Account is awaiting admin approval")
        return {
            "token": make_token(user),
            "user": {"email": user.email, "name": user.name, "role": user.role},
            "status": user.status,
        }


@app.post("/api/auth/forgot-password")
def forgot_password(body: EmailRequest):
    email = body.email.strip().lower()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        now = datetime.now(timezone.utc)
        if not user or user.status == "UNVERIFIED" or (user.otp_purpose == "RESET" and user.otp_sent_at and now - aware(user.otp_sent_at) < timedelta(minutes=1)):
            return {"message": "If that account exists, a reset code has been sent."}

        otp = prepare_otp(user, email, "RESET", now)
        try:
            send_otp(email, otp, "RESET")
            db.commit()
        except (KeyError, OSError, smtplib.SMTPException):
            raise HTTPException(503, "Email service is unavailable")
    return {"message": "If that account exists, a reset code has been sent."}


@app.post("/api/auth/reset-password")
def reset_password(body: PasswordReset):
    email = body.email.strip().lower()
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        now = datetime.now(timezone.utc)
        valid = bool(
            user
            and user.otp_purpose == "RESET"
            and user.otp_digest
            and user.otp_expires
            and aware(user.otp_expires) > now
            and (user.otp_attempts or 0) > 0
            and hmac.compare_digest(user.otp_digest, otp_hash(email, body.otp))
        )
        if not valid:
            if user and (user.otp_attempts or 0) > 0:
                user.otp_attempts -= 1
                db.commit()
            raise HTTPException(400, "Invalid or expired reset code")

        user.password_hash = hash_password(body.password)
        user.otp_digest = None
        user.otp_purpose = None
        user.otp_expires = None
        user.otp_attempts = 0
        db.commit()
    return {"message": "Password updated. You can now sign in."}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email, "name": user.name, "role": user.role}


@app.get("/api/admin/teachers")
def pending_teachers(_: User = Depends(admin_user)):
    with Session(engine) as db:
        teachers = db.scalars(
            select(User).where(User.role == "TEACHER", User.status == "PENDING").order_by(User.name)
        ).all()
        return [{"id": user.id, "name": user.name, "email": user.email} for user in teachers]


@app.patch("/api/admin/teachers/{teacher_id}")
def decide_teacher(teacher_id: int, body: TeacherDecision, _: User = Depends(admin_user)):
    with Session(engine) as db:
        teacher = db.get(User, teacher_id)
        if not teacher or teacher.role != "TEACHER" or teacher.status != "PENDING":
            raise HTTPException(404, "Pending teacher not found")
        status = "ACTIVE" if body.action != "REJECT" else "REJECTED"
        if body.action == "MAKE_ADMIN":
            teacher.role = "DEPARTMENT_ADMIN"
        teacher.status = status
        db.commit()
    return {"status": status}


@app.post("/api/admin/academic-setup", status_code=201)
def create_academic_setup(body: AcademicSetup, _: User = Depends(admin_user)):
    with Session(engine) as db:
        program = db.scalar(select(Program).where(Program.code == body.program_code.upper()))
        if not program:
            program = Program(code=body.program_code.upper(), name=body.program_name.strip())
            db.add(program)
            db.flush()
        academic_session = db.scalar(select(AcademicSession).where(AcademicSession.name == body.academic_session))
        if not academic_session:
            academic_session = AcademicSession(name=body.academic_session.strip())
            db.add(academic_session)
            db.flush()
        batch = db.scalar(
            select(Batch).where(Batch.program_id == program.id, Batch.code == body.batch_code)
        )
        if not batch:
            batch = Batch(
                code=body.batch_code.strip(),
                name=body.batch_name.strip(),
                program_id=program.id,
                session_id=academic_session.id,
            )
            db.add(batch)
            db.flush()
        semester = db.scalar(select(Semester).where(Semester.number == body.semester_number))
        if not semester:
            semester = Semester(number=body.semester_number, name=body.semester_name.strip())
            db.add(semester)
            db.flush()
        course = db.scalar(select(Course).where(Course.code == body.course_code.upper()))
        if not course:
            course = Course(
                code=body.course_code.upper(),
                name=body.course_name.strip(),
                credits=body.credits,
                semester_id=semester.id,
            )
            db.add(course)
        if body.hall_name and not db.scalar(select(Hall).where(Hall.name == body.hall_name.strip())):
            db.add(Hall(name=body.hall_name.strip()))
        students = db.scalars(
            select(StudentProfile).where(
                StudentProfile.program == program.code, StudentProfile.batch == batch.code
            )
        )
        for student in students:
            student.batch_id = batch.id
            for classroom_id in db.scalars(
                select(Classroom.id).where(
                    Classroom.batch_id == batch.id, Classroom.status == "ACTIVE"
                )
            ):
                enrolled = db.scalar(
                    select(ClassroomEnrollment.id).where(
                        ClassroomEnrollment.classroom_id == classroom_id,
                        ClassroomEnrollment.student_id == student.user_id,
                    )
                )
                if not enrolled:
                    db.add(
                        ClassroomEnrollment(
                            classroom_id=classroom_id, student_id=student.user_id
                        )
                    )
        try:
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "Academic item already exists")
    return {"message": "Academic data saved"}


@app.get("/api/academics")
def academics(_: User = Depends(current_user)):
    with Session(engine) as db:
        return {
            "programs": [{"id": x.id, "code": x.code, "name": x.name} for x in db.scalars(select(Program))],
            "sessions": [{"id": x.id, "name": x.name} for x in db.scalars(select(AcademicSession))],
            "batches": [
                {"id": x.id, "code": x.code, "name": x.name, "program_id": x.program_id, "session_id": x.session_id}
                for x in db.scalars(select(Batch).where(Batch.status == "ACTIVE"))
            ],
            "semesters": [{"id": x.id, "number": x.number, "name": x.name} for x in db.scalars(select(Semester))],
            "courses": [
                {"id": x.id, "code": x.code, "name": x.name, "credits": x.credits, "semester_id": x.semester_id}
                for x in db.scalars(select(Course))
            ],
            "halls": [{"id": x.id, "name": x.name} for x in db.scalars(select(Hall))],
        }


def profile_data(profile: StudentProfile) -> dict:
    return {
        "program": profile.program,
        "batch": profile.batch,
        "roll": profile.roll,
        "batch_id": profile.batch_id,
        "phone": profile.phone or "",
        "hall_id": profile.hall_id,
        "hometown_district": profile.hometown_district or "",
        "current_address": profile.current_address or "",
        "blood_group": profile.blood_group,
        "last_blood_donation": profile.last_blood_donation,
        "profile_completed": profile.profile_completed,
    }


@app.get("/api/student/profile")
def read_profile(user: User = Depends(student_user)):
    with Session(engine) as db:
        return profile_data(get_student(db, user.id))


@app.put("/api/student/profile")
def update_profile(body: StudentProfileUpdate, user: User = Depends(student_user)):
    with Session(engine) as db:
        profile = get_student(db, user.id)
        if body.hall_id and not db.get(Hall, body.hall_id):
            raise HTTPException(400, "Hall not found")
        for field, value in body.model_dump().items():
            setattr(profile, field, value)
        profile.profile_completed = True
        db.commit()
        db.refresh(profile)
        return profile_data(profile)


@app.post("/api/admin/cr-positions", status_code=201)
def create_cr_position(body: CRPositionCreate, _: User = Depends(admin_user)):
    with Session(engine) as db:
        if not db.get(Batch, body.batch_id):
            raise HTTPException(400, "Batch not found")
        position = CRPosition(**body.model_dump())
        db.add(position)
        db.commit()
        db.refresh(position)
        return {"id": position.id, "title": position.title, "seats": position.seats}


@app.get("/api/cr-positions")
def cr_positions(_: User = Depends(current_user)):
    with Session(engine) as db:
        return [
            {"id": item.id, "batch_id": item.batch_id, "title": item.title, "seats": item.seats}
            for item in db.scalars(select(CRPosition).order_by(CRPosition.title))
        ]


@app.post("/api/admin/elections", status_code=201)
def create_election(body: ElectionCreate, user: User = Depends(admin_user)):
    if not (
        aware(body.nomination_start)
        < aware(body.nomination_end)
        <= aware(body.voting_start)
        < aware(body.voting_end)
    ):
        raise HTTPException(400, "Election dates are not in order")
    with Session(engine) as db:
        if not db.get(CRPosition, body.position_id):
            raise HTTPException(400, "CR position not found")
        election = CRElection(**body.model_dump(), created_by=user.id)
        db.add(election)
        db.commit()
        db.refresh(election)
        return {"id": election.id, "status": election.status}


@app.get("/api/elections")
def elections(user: User = Depends(current_user)):
    with Session(engine) as db:
        statement = select(CRElection, CRPosition).join(CRPosition)
        profile = db.get(StudentProfile, user.id) if user.role == "STUDENT" else None
        if profile:
            statement = statement.where(CRPosition.batch_id == profile.batch_id)
        output = []
        for election, position in db.execute(statement.order_by(CRElection.voting_end.desc())):
            candidates = db.execute(
                select(CRCandidate, User)
                .join(User, User.id == CRCandidate.student_id)
                .where(CRCandidate.election_id == election.id)
                .order_by(User.name)
            ).all()
            now = datetime.now(timezone.utc)
            status = election.status
            if status != "CLOSED":
                if now < aware(election.nomination_start):
                    status = "UPCOMING"
                elif now <= aware(election.nomination_end):
                    status = "NOMINATION"
                elif now < aware(election.voting_start):
                    status = "CANDIDATES_FINALIZED"
                elif now <= aware(election.voting_end):
                    status = "VOTING"
                else:
                    status = "AWAITING_RESULT"
            item = {
                "id": election.id,
                "title": election.title,
                "position": position.title,
                "batch_id": position.batch_id,
                "seats": position.seats,
                "nomination_start": election.nomination_start,
                "nomination_end": election.nomination_end,
                "voting_start": election.voting_start,
                "voting_end": election.voting_end,
                "status": status,
                "candidates": [
                    {"id": candidate.id, "name": candidate_user.name, "manifesto": candidate.manifesto, "status": candidate.status}
                    for candidate, candidate_user in candidates
                ],
            }
            if profile:
                item["has_voted"] = bool(
                    db.scalar(
                        select(ElectionParticipation.id).where(
                            ElectionParticipation.election_id == election.id,
                            ElectionParticipation.voter_id == user.id,
                        )
                    )
                )
            if election.status == "CLOSED":
                item["results"] = [
                    {"candidate_id": candidate_id, "votes": votes}
                    for candidate_id, votes in db.execute(
                        select(CRBallot.candidate_id, func.count(CRBallot.id))
                        .where(CRBallot.election_id == election.id)
                        .group_by(CRBallot.candidate_id)
                    )
                ]
            output.append(item)
        return output


@app.post("/api/elections/{election_id}/nominate", status_code=201)
def nominate(election_id: int, body: NominationCreate, user: User = Depends(student_user)):
    with Session(engine) as db:
        election = db.get(CRElection, election_id)
        position = db.get(CRPosition, election.position_id) if election else None
        profile = get_student(db, user.id)
        now = datetime.now(timezone.utc)
        if not election or not position or profile.batch_id != position.batch_id:
            raise HTTPException(403, "Not eligible for this election")
        if not (aware(election.nomination_start) <= now <= aware(election.nomination_end)):
            raise HTTPException(400, "Nominations are closed")
        db.add(CRCandidate(election_id=election_id, student_id=user.id, manifesto=body.manifesto.strip()))
        try:
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "Already nominated")
    return {"status": "PENDING"}


@app.patch("/api/admin/candidates/{candidate_id}")
def decide_candidate(candidate_id: int, body: CandidateDecision, _: User = Depends(admin_user)):
    with Session(engine) as db:
        candidate = db.get(CRCandidate, candidate_id)
        if not candidate or candidate.status != "PENDING":
            raise HTTPException(404, "Pending candidate not found")
        status = "APPROVED" if body.action == "APPROVE" else "REJECTED"
        candidate.status = status
        db.commit()
    return {"status": status}


@app.post("/api/elections/{election_id}/vote", status_code=201)
def vote(election_id: int, body: VoteCreate, user: User = Depends(student_user)):
    with Session(engine) as db:
        election = db.get(CRElection, election_id)
        position = db.get(CRPosition, election.position_id) if election else None
        candidate = db.get(CRCandidate, body.candidate_id)
        profile = get_student(db, user.id)
        now = datetime.now(timezone.utc)
        if not election or election.status == "CLOSED" or not position or profile.batch_id != position.batch_id:
            raise HTTPException(403, "Not eligible for this election")
        if not (aware(election.voting_start) <= now <= aware(election.voting_end)):
            raise HTTPException(400, "Voting is closed")
        if not candidate or candidate.election_id != election_id or candidate.status != "APPROVED":
            raise HTTPException(400, "Candidate is not eligible")
        db.add(ElectionParticipation(election_id=election_id, voter_id=user.id))
        db.add(CRBallot(election_id=election_id, candidate_id=candidate.id))
        try:
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "You already voted")
    return {"message": "Vote recorded"}


@app.post("/api/admin/elections/{election_id}/close")
def close_election(election_id: int, _: User = Depends(admin_user)):
    with Session(engine) as db:
        election = db.get(CRElection, election_id)
        if not election or election.status == "CLOSED":
            raise HTTPException(404, "Open election not found")
        if datetime.now(timezone.utc) < aware(election.voting_end):
            raise HTTPException(400, "Voting has not ended")
        position = db.get(CRPosition, election.position_id)
        winners = db.execute(
            select(CRCandidate.student_id, func.count(CRBallot.id).label("votes"))
            .join(CRBallot, CRBallot.candidate_id == CRCandidate.id)
            .where(CRCandidate.election_id == election_id, CRCandidate.status == "APPROVED")
            .group_by(CRCandidate.student_id)
            .order_by(text("votes DESC"), CRCandidate.student_id)
            .limit(position.seats)
        ).all()
        for student_id, _ in winners:
            db.add(
                CRAppointment(
                    election_id=election.id,
                    position_id=position.id,
                    student_id=student_id,
                )
            )
        election.status = "CLOSED"
        db.commit()
    return {"winners": [student_id for student_id, _ in winners]}


def can_manage_classroom(user: User, classroom: Classroom) -> bool:
    return user.role in {"SUPER_ADMIN", "DEPARTMENT_ADMIN"} or classroom.teacher_id == user.id


@app.post("/api/classrooms", status_code=201)
def create_classroom(body: ClassroomCreate, user: User = Depends(teacher_or_admin)):
    with Session(engine) as db:
        teacher_id = body.teacher_id if user.role in {"SUPER_ADMIN", "DEPARTMENT_ADMIN"} else user.id
        teacher = db.get(User, teacher_id)
        course = db.get(Course, body.course_id)
        if not teacher or teacher.role != "TEACHER" or teacher.status != "ACTIVE":
            raise HTTPException(400, "Active teacher not found")
        if not course or course.semester_id != body.semester_id:
            raise HTTPException(400, "Course and semester do not match")
        if not db.get(Batch, body.batch_id) or not db.get(AcademicSession, body.session_id):
            raise HTTPException(400, "Batch or academic session not found")
        classroom = Classroom(**body.model_dump(exclude={"teacher_id"}), teacher_id=teacher_id)
        db.add(classroom)
        try:
            db.flush()
            for student_id in db.scalars(
                select(StudentProfile.user_id).where(StudentProfile.batch_id == body.batch_id)
            ):
                db.add(ClassroomEnrollment(classroom_id=classroom.id, student_id=student_id))
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "Classroom already exists")
        db.refresh(classroom)
        return {"id": classroom.id, "enrolled": db.scalar(select(func.count()).where(ClassroomEnrollment.classroom_id == classroom.id))}


@app.get("/api/classrooms")
def classrooms(user: User = Depends(current_user)):
    with Session(engine) as db:
        statement = select(Classroom)
        if user.role == "STUDENT":
            statement = statement.join(ClassroomEnrollment).where(ClassroomEnrollment.student_id == user.id)
        elif user.role == "TEACHER":
            statement = statement.where(Classroom.teacher_id == user.id)
        output = []
        for classroom in db.scalars(statement.where(Classroom.status == "ACTIVE")):
            course = db.get(Course, classroom.course_id)
            batch = db.get(Batch, classroom.batch_id)
            teacher = db.get(User, classroom.teacher_id)
            output.append(
                {
                    "id": classroom.id,
                    "course_id": course.id,
                    "course_code": course.code,
                    "course_name": course.name,
                    "batch_id": batch.id,
                    "batch_name": batch.name,
                    "teacher_id": teacher.id,
                    "teacher_name": teacher.name,
                    "semester_id": classroom.semester_id,
                    "session_id": classroom.session_id,
                    "section": classroom.section,
                }
            )
        return output


@app.post("/api/classrooms/{classroom_id}/sessions", status_code=201)
def create_class_session(
    classroom_id: int, body: ClassSessionCreate, user: User = Depends(teacher_or_admin)
):
    if body.starts_at >= body.ends_at:
        raise HTTPException(400, "End time must be after start time")
    with Session(engine) as db:
        classroom = db.get(Classroom, classroom_id)
        if not classroom or not can_manage_classroom(user, classroom):
            raise HTTPException(403, "Cannot manage this classroom")
        class_session = ClassSession(classroom_id=classroom_id, **body.model_dump())
        db.add(class_session)
        db.commit()
        db.refresh(class_session)
        return {"id": class_session.id}


@app.get("/api/classrooms/{classroom_id}/sessions")
def classroom_sessions(classroom_id: int, user: User = Depends(current_user)):
    with Session(engine) as db:
        classroom = db.get(Classroom, classroom_id)
        enrolled = db.scalar(
            select(ClassroomEnrollment.id).where(
                ClassroomEnrollment.classroom_id == classroom_id,
                ClassroomEnrollment.student_id == user.id,
            )
        )
        if not classroom or not (enrolled or can_manage_classroom(user, classroom)):
            raise HTTPException(403, "Cannot view this classroom")
        sessions = []
        for class_session in db.scalars(
            select(ClassSession)
            .where(ClassSession.classroom_id == classroom_id)
            .order_by(ClassSession.session_date.desc(), ClassSession.starts_at.desc())
        ):
            records = db.execute(
                select(AttendanceRecord, User)
                .join(User, User.id == AttendanceRecord.student_id)
                .where(AttendanceRecord.class_session_id == class_session.id)
                .order_by(User.email)
            ).all()
            sessions.append(
                {
                    "id": class_session.id,
                    "date": class_session.session_date,
                    "starts_at": class_session.starts_at,
                    "ends_at": class_session.ends_at,
                    "topic": class_session.topic,
                    "attendance": [
                        {"student_id": record.student_id, "name": record_user.name, "email": record_user.email, "status": record.status}
                        for record, record_user in records
                        if can_manage_classroom(user, classroom) or record.student_id == user.id
                    ],
                }
            )
        if can_manage_classroom(user, classroom):
            roster = db.execute(
                select(User.id, User.name, User.email)
                .join(ClassroomEnrollment, ClassroomEnrollment.student_id == User.id)
                .where(ClassroomEnrollment.classroom_id == classroom_id)
                .order_by(User.email)
            ).all()
            return {"sessions": sessions, "roster": [dict(row._mapping) for row in roster]}
        return {"sessions": sessions}


@app.put("/api/sessions/{class_session_id}/attendance")
def save_attendance(
    class_session_id: int, body: AttendanceUpdate, user: User = Depends(teacher_or_admin)
):
    with Session(engine) as db:
        class_session = db.get(ClassSession, class_session_id)
        classroom = db.get(Classroom, class_session.classroom_id) if class_session else None
        if not classroom or not can_manage_classroom(user, classroom):
            raise HTTPException(403, "Cannot manage this classroom")
        for item in body.records:
            enrolled = db.scalar(
                select(ClassroomEnrollment.id).where(
                    ClassroomEnrollment.classroom_id == classroom.id,
                    ClassroomEnrollment.student_id == item.student_id,
                    ClassroomEnrollment.status == "ACTIVE",
                )
            )
            if not enrolled:
                raise HTTPException(400, f"Student {item.student_id} is not enrolled")
            record = db.scalar(
                select(AttendanceRecord).where(
                    AttendanceRecord.class_session_id == class_session_id,
                    AttendanceRecord.student_id == item.student_id,
                )
            )
            if not record:
                db.add(
                    AttendanceRecord(
                        class_session_id=class_session_id,
                        student_id=item.student_id,
                        status=item.status,
                    )
                )
            elif record.status != item.status:
                old_status = record.status
                record.status = item.status
                db.add(
                    AttendanceAudit(
                        attendance_id=record.id,
                        old_status=old_status,
                        new_status=item.status,
                        changed_by=user.id,
                    )
                )
        db.commit()
    return {"message": "Attendance saved"}


@app.get("/api/student/attendance")
def attendance_summary(user: User = Depends(student_user)):
    with Session(engine) as db:
        summaries = []
        classroom_ids = db.scalars(
            select(ClassroomEnrollment.classroom_id).where(
                ClassroomEnrollment.student_id == user.id,
                ClassroomEnrollment.status == "ACTIVE",
            )
        )
        for classroom_id in classroom_ids:
            classroom = db.get(Classroom, classroom_id)
            course = db.get(Course, classroom.course_id)
            counts = dict(
                db.execute(
                    select(AttendanceRecord.status, func.count(AttendanceRecord.id))
                    .join(ClassSession)
                    .where(
                        ClassSession.classroom_id == classroom_id,
                        AttendanceRecord.student_id == user.id,
                    )
                    .group_by(AttendanceRecord.status)
                ).all()
            )
            held = sum(counts.values())
            # ponytail: late/excused count fully; add department weights when policy exists.
            attended = counts.get("PRESENT", 0) + counts.get("LATE", 0) + counts.get("EXCUSED", 0)
            summaries.append(
                {
                    "classroom_id": classroom_id,
                    "course": f"{course.code} — {course.name}",
                    "held": held,
                    "present": counts.get("PRESENT", 0),
                    "absent": counts.get("ABSENT", 0),
                    "late": counts.get("LATE", 0),
                    "excused": counts.get("EXCUSED", 0),
                    "percentage": round(attended / held * 100, 1) if held else 0,
                }
            )
        return summaries


@app.post("/api/complaints", status_code=201)
def create_complaint(body: ComplaintCreate, user: User = Depends(current_user)):
    with Session(engine) as db:
        complaint = Complaint(submitter_id=user.id, **body.model_dump())
        db.add(complaint)
        db.commit()
        db.refresh(complaint)
        return {"id": complaint.id, "status": complaint.status}


@app.get("/api/complaints")
def complaints(user: User = Depends(current_user)):
    with Session(engine) as db:
        statement = select(Complaint).order_by(Complaint.created_at.desc())
        is_admin = user.role in {"SUPER_ADMIN", "DEPARTMENT_ADMIN"}
        if not is_admin:
            statement = statement.where(Complaint.submitter_id == user.id)
        output = []
        for complaint in db.scalars(statement):
            item = {
                "id": complaint.id,
                "category": complaint.category,
                "subject": complaint.subject,
                "details": complaint.details,
                "confidential": complaint.confidential,
                "status": complaint.status,
                "created_at": complaint.created_at,
            }
            if is_admin:
                submitter = db.get(User, complaint.submitter_id)
                item["submitter"] = {"name": submitter.name, "email": submitter.email}
            output.append(item)
        return output


@app.patch("/api/admin/complaints/{complaint_id}")
def update_complaint(
    complaint_id: int, body: ComplaintDecision, _: User = Depends(admin_user)
):
    with Session(engine) as db:
        complaint = db.get(Complaint, complaint_id)
        if not complaint:
            raise HTTPException(404, "Complaint not found")
        transitions = {
            "SUBMITTED": "ACKNOWLEDGED",
            "ACKNOWLEDGED": "UNDER_REVIEW",
            "UNDER_REVIEW": "ASSIGNED",
            "ASSIGNED": "ACTION_TAKEN",
            "ACTION_TAKEN": "RESOLVED",
        }
        if transitions.get(complaint.status) != body.status:
            raise HTTPException(400, "Complaint status must follow the workflow")
        complaint.status = body.status
        db.commit()
    return {"status": body.status}


@app.post("/api/classrooms/{classroom_id}/feedback", status_code=201)
def submit_feedback(
    classroom_id: int, body: FeedbackCreate, user: User = Depends(student_user)
):
    with Session(engine) as db:
        enrolled = db.scalar(
            select(ClassroomEnrollment.id).where(
                ClassroomEnrollment.classroom_id == classroom_id,
                ClassroomEnrollment.student_id == user.id,
                ClassroomEnrollment.status == "ACTIVE",
            )
        )
        if not enrolled:
            raise HTTPException(403, "You are not enrolled in this classroom")
        db.add(Feedback(classroom_id=classroom_id, student_id=user.id, **body.model_dump()))
        try:
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "Feedback already submitted")
    return {"message": "Feedback submitted anonymously"}


@app.get("/api/classrooms/{classroom_id}/feedback")
def feedback_summary(classroom_id: int, user: User = Depends(teacher_or_admin)):
    with Session(engine) as db:
        classroom = db.get(Classroom, classroom_id)
        if not classroom or not can_manage_classroom(user, classroom):
            raise HTTPException(403, "Cannot view this feedback")
        count, clarity, organization, fairness, regularity, interaction = db.execute(
            select(
                func.count(Feedback.id),
                func.avg(Feedback.clarity),
                func.avg(Feedback.organization),
                func.avg(Feedback.fairness),
                func.avg(Feedback.regularity),
                func.avg(Feedback.interaction),
            ).where(Feedback.classroom_id == classroom_id)
        ).one()
        comments = db.scalars(
            select(Feedback.comment).where(
                Feedback.classroom_id == classroom_id, Feedback.comment != ""
            )
        ).all()
        return {
            "responses": count,
            "ratings": {
                "clarity": round(float(clarity), 1) if clarity else 0,
                "organization": round(float(organization), 1) if organization else 0,
                "fairness": round(float(fairness), 1) if fairness else 0,
                "regularity": round(float(regularity), 1) if regularity else 0,
                "interaction": round(float(interaction), 1) if interaction else 0,
            },
            "comments": comments,
        }
