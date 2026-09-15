import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("SUPER_ADMIN_EMAIL", "admin@iit.du.ac.bd")

from api.index import (
    EmailRequest,
    OtpRequest,
    PasswordReset,
    Signin,
    Signup,
    TeacherDecision,
    User,
    admin_user,
    classify_email,
    decide_teacher,
    engine,
    forgot_password,
    hash_password,
    otp_hash,
    pending_teachers,
    reset_password,
    signin,
    signup,
    verify_email,
    verify_password,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException


class EmailPolicyTest(unittest.TestCase):
    @patch("api.index.send_otp")
    def test_signup_signin_and_password_reset(self, send_otp):
        email = "bsse9999@iit.du.ac.bd"
        signup(Signup(name="Test Student", email=email, password="old-password"))
        verify_code = send_otp.call_args.args[1]
        self.assertTrue(verify_email(OtpRequest(email=email, otp=verify_code))["token"])
        self.assertTrue(signin(Signin(email=email, password="old-password"))["token"])

        forgot_password(EmailRequest(email=email))
        reset_code = send_otp.call_args.args[1]
        reset_password(PasswordReset(email=email, otp=reset_code, password="new-password"))
        self.assertTrue(signin(Signin(email=email, password="new-password"))["token"])

    @patch("api.index.send_otp")
    def test_super_admin_approves_teacher(self, send_otp):
        signup(Signup(name="Admin", email="admin@iit.du.ac.bd", password="admin-password"))
        admin_code = send_otp.call_args.args[1]
        verify_email(OtpRequest(email="admin@iit.du.ac.bd", otp=admin_code))

        signup(Signup(name="Teacher", email="teacher@iit.du.ac.bd", password="teacher-password"))
        teacher_code = send_otp.call_args.args[1]
        verify_email(OtpRequest(email="teacher@iit.du.ac.bd", otp=teacher_code))

        with Session(engine) as db:
            admin = db.scalar(select(User).where(User.email == "admin@iit.du.ac.bd"))
            db.expunge(admin)
        teacher = pending_teachers(admin)[0]
        decide_teacher(teacher["id"], TeacherDecision(action="APPROVE"), admin)
        self.assertTrue(signin(Signin(email="teacher@iit.du.ac.bd", password="teacher-password"))["token"])
        with Session(engine) as db:
            teacher_user = db.scalar(select(User).where(User.email == "teacher@iit.du.ac.bd"))
            db.expunge(teacher_user)
        with self.assertRaises(HTTPException):
            admin_user(teacher_user)

    def test_student_identity_is_parsed(self):
        role, status, profile = classify_email("bsse1501@iit.du.ac.bd")
        self.assertEqual((role, status), ("STUDENT", "ACTIVE"))
        self.assertEqual(profile, {"program": "BSSE", "batch": "15", "roll": "01"})

    def test_staff_requires_approval(self):
        self.assertEqual(classify_email("teacher@iit.du.ac.bd")[:2], ("TEACHER", "PENDING"))

    def test_external_email_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_email("student@gmail.com")

    def test_password_hashing(self):
        encoded = hash_password("correct horse battery staple")
        self.assertTrue(verify_password("correct horse battery staple", encoded))
        self.assertFalse(verify_password("wrong password", encoded))

    def test_otp_is_bound_to_email(self):
        self.assertNotEqual(otp_hash("one@iit.du.ac.bd", "123456"), otp_hash("two@iit.du.ac.bd", "123456"))
        self.assertNotEqual(otp_hash("one@iit.du.ac.bd", "123456"), otp_hash("one@iit.du.ac.bd", "123456", "VERIFY"))


if __name__ == "__main__":
    unittest.main()
