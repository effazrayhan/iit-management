import os
import unittest
from unittest.mock import patch
from fastapi import Response

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("SUPER_ADMIN_EMAIL", "admin@iit.du.ac.bd")

from api.index import (
    EmailRequest,
    OtpRequest,
    PasswordReset,
    Signin,
    Signup,
    batch_from_session,
    classify_email,
    forgot_password,
    hash_password,
    otp_hash,
    reset_password,
    session_from_batch,
    signin,
    signup,
    verify_email,
    verify_password,
)


class EmailPolicyTest(unittest.TestCase):
    @patch("api.index.send_otp")
    def test_signup_signin_and_password_reset(self, send_otp):
        email = "bsse9999@iit.du.ac.bd"
        signup(Signup(name="Test Student", email=email, password="old-password"))
        verify_code = send_otp.call_args.args[1]
        self.assertEqual(verify_email(OtpRequest(email=email, otp=verify_code), Response())["status"], "ACTIVE")
        response = Response()
        self.assertEqual(signin(Signin(email=email, password="old-password"), response)["status"], "ACTIVE")
        self.assertIn("HttpOnly", response.headers["set-cookie"])

        forgot_password(EmailRequest(email=email))
        reset_code = send_otp.call_args.args[1]
        reset_password(PasswordReset(email=email, otp=reset_code, password="new-password"))
        self.assertEqual(signin(Signin(email=email, password="new-password"), Response())["status"], "ACTIVE")

    def test_student_identity_is_parsed(self):
        role, status, profile = classify_email("bsse1501@iit.du.ac.bd")
        self.assertEqual((role, status), ("STUDENT", "ACTIVE"))
        self.assertEqual(profile, {"program": "BSSE", "batch": "15", "roll": "01"})
        self.assertEqual(session_from_batch(profile["batch"]), "22-23")
        self.assertEqual(batch_from_session("22-23"), "15")
        self.assertEqual(batch_from_session("2022-23"), "15")

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
