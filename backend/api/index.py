import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.auth.transport import requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy import ForeignKey, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

load_dotenv(Path(__file__).parents[2] / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
JWT_SECRET = os.environ["JWT_SECRET"]
STUDENT_EMAIL_PATTERN = os.getenv(
    "STUDENT_EMAIL_PATTERN",
    r"^bsse(?P<batch>\d{2})(?P<roll>\d{2})@iit\.du\.ac\.bd$",
)
STAFF_EMAIL_DOMAIN = os.getenv("STAFF_EMAIL_DOMAIN", "iit.du.ac.bd")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    program: Mapped[str] = mapped_column(String(20))
    batch: Mapped[str] = mapped_column(String(2))
    roll: Mapped[str] = mapped_column(String(2))


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Base.metadata.create_all(engine)

app = FastAPI(title="IIT Management API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GoogleLogin(BaseModel):
    credential: str


def classify_email(email: str) -> tuple[str, str, dict[str, str] | None]:
    email = email.lower()
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
        db.expunge(user)
        return user


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/google")
def google_login(body: GoogleLogin):
    try:
        identity = id_token.verify_oauth2_token(
            body.credential, requests.Request(), GOOGLE_CLIENT_ID
        )
        if not identity.get("email_verified"):
            raise ValueError("Email is not verified")
        email = identity["email"].lower()
        role, status, student = classify_email(email)
    except ValueError as error:
        raise HTTPException(401, str(error))

    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                email=email,
                name=identity.get("name", email.split("@", 1)[0]),
                role=role,
                status=status,
            )
            db.add(user)
            db.flush()
            if student:
                db.add(StudentProfile(user_id=user.id, **student))
            db.commit()
            db.refresh(user)

        return {
            "token": make_token(user) if user.status == "ACTIVE" else None,
            "user": {"email": user.email, "name": user.name, "role": user.role},
            "status": user.status,
        }


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email, "name": user.name, "role": user.role}
