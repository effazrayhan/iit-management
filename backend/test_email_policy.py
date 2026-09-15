import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("JWT_SECRET", "test")

from api.index import classify_email


class EmailPolicyTest(unittest.TestCase):
    def test_student_identity_is_parsed(self):
        role, status, profile = classify_email("bsse1501@iit.du.ac.bd")
        self.assertEqual((role, status), ("STUDENT", "ACTIVE"))
        self.assertEqual(profile, {"program": "BSSE", "batch": "15", "roll": "01"})

    def test_staff_requires_approval(self):
        self.assertEqual(classify_email("teacher@iit.du.ac.bd")[:2], ("TEACHER", "PENDING"))

    def test_external_email_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_email("student@gmail.com")


if __name__ == "__main__":
    unittest.main()
