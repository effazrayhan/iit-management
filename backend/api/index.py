import base64
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Literal

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, create_engine, select, text
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
    action: Literal["APPROVE", "REJECT"]


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
                db.add(StudentProfile(user_id=user.id, **student))
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
        status = "ACTIVE" if body.action == "APPROVE" else "REJECTED"
        teacher.status = status
        db.commit()
    return {"status": status}
