import os
import unittest
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test"
os.environ["SUPER_ADMIN_EMAIL"] = "admin@iit.du.ac.bd"

from fastapi import HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.index import (
    AcademicSetup,
    AttendanceAudit,
    AttendanceItem,
    AttendanceUpdate,
    Batch,
    CRCandidate,
    CRElection,
    CRPositionCreate,
    CandidateDecision,
    ClassPostCreate,
    ClassSessionCreate,
    ClassroomCreate,
    ComplaintCreate,
    ComplaintDecision,
    Course,
    CourseSetup,
    ElectionCreate,
    FeedbackCreate,
    NominationCreate,
    OtpRequest,
    RecurringCancellationCreate,
    RecurringClassCreate,
    RecurringOccurrence,
    Signup,
    StudentProfileUpdate,
    StaffDecision,
    TeacherDecision,
    User,
    VoteCreate,
    admin_user,
    administer_user,
    administrative_users,
    attendance_summary,
    audit_log,
    close_election,
    cancel_recurring_class,
    classroom_posts,
    create_academic_setup,
    create_class_session,
    create_classroom,
    create_class_post,
    create_complaint,
    create_cr_position,
    create_election,
    create_recurring_class,
    decide_candidate,
    decide_teacher,
    dashboard,
    donors,
    engine,
    nominate,
    notifications,
    save_attendance,
    signup,
    start_recurring_class,
    submit_feedback,
    update_complaint,
    update_profile,
    verify_email,
    vote,
)


class PhaseFlowTest(unittest.TestCase):
    @patch("api.index.send_otp")
    def test_phases_two_through_six(self, send_otp):
        def register(name, email, password="test-password"):
            signup(Signup(name=name, email=email, password=password))
            verify_email(OtpRequest(email=email, otp=send_otp.call_args.args[1]), Response())
            with Session(engine) as db:
                user = db.scalar(select(User).where(User.email == email))
                db.expunge(user)
                return user

        admin = register("Admin", "admin@iit.du.ac.bd")
        teacher = register("Teacher", "teacher2@iit.du.ac.bd")
        decide_teacher(teacher.id, TeacherDecision(action="APPROVE"), admin)
        teacher.status = "ACTIVE"
        self.assertTrue(any(member["email"] == teacher.email for member in administrative_users(admin)))
        self.assertEqual(
            administer_user(teacher.id, StaffDecision(action="MAKE_ADMIN"), admin)["role"],
            "DEPARTMENT_ADMIN",
        )
        self.assertEqual(
            administer_user(teacher.id, StaffDecision(action="MAKE_TEACHER"), admin)["role"],
            "TEACHER",
        )
        student_one = register("Student 01", "bsse1501@iit.du.ac.bd")
        student_two = register("Student 02", "bsse1502@iit.du.ac.bd")

        self.assertTrue(
            update_profile(
                StudentProfileUpdate(
                    phone="01700000000",
                    current_address="Dhaka",
                    blood_group="O+",
                    donor_available=True,
                    donor_contact_visible=True,
                ),
                student_one,
            )["profile_completed"]
        )
        with Session(engine) as db:
            batch = db.scalar(select(Batch).where(Batch.code == "15"))
            batch_id, session_id = batch.id, batch.session_id

        position = create_cr_position(
            CRPositionCreate(batch_id=batch_id, title="General CR", seats=1), admin
        )
        now = datetime.now(timezone.utc)
        election = create_election(
            ElectionCreate(
                position_id=position["id"],
                title="CR Election",
                nomination_start=now - timedelta(hours=1),
                nomination_end=now + timedelta(hours=1),
                voting_start=now + timedelta(hours=2),
                voting_end=now + timedelta(hours=3),
            ),
            admin,
        )
        nominate(election["id"], NominationCreate(manifesto="Serve the batch"), student_one)
        with Session(engine) as db:
            candidate_id = db.scalar(
                select(CRCandidate.id).where(CRCandidate.election_id == election["id"])
            )
        decide_candidate(candidate_id, CandidateDecision(action="APPROVE"), admin)
        with Session(engine) as db:
            stored = db.get(CRElection, election["id"])
            stored.voting_start, stored.voting_end = now - timedelta(minutes=1), now + timedelta(minutes=1)
            db.commit()
        vote(election["id"], VoteCreate(candidate_id=candidate_id), student_two)
        with Session(engine) as db:
            stored = db.get(CRElection, election["id"])
            stored.voting_end = now - timedelta(seconds=1)
            db.commit()
        self.assertEqual(close_election(election["id"], admin)["winners"], [student_one.id])

        academic_result = create_academic_setup(
            AcademicSetup(
                batch_name="Code Fifteen",
                semester_number=5,
                courses=[
                    CourseSetup(course_code="SE-301", course_name="Software Architecture", credits=3),
                    CourseSetup(course_code="SE-302", course_name="Software Testing", credits=2),
                ],
            ),
            student_one,
        )
        self.assertEqual(academic_result["session"], "22-23")
        self.assertEqual(len(academic_result["courses"]), 2)
        with Session(engine) as db:
            batch = db.get(Batch, batch_id)
            course = db.scalar(select(Course).where(Course.code == "SE-301"))
            self.assertEqual(batch.name, "Code Fifteen")
            self.assertEqual(batch.current_semester_id, course.semester_id)
            course_id, semester_id = course.id, course.semester_id

        classroom = create_classroom(
            ClassroomCreate(
                course_id=course_id,
                batch_id=batch_id,
                semester_id=semester_id,
                session_id=session_id,
            ),
            teacher,
        )
        create_class_post(
            classroom["id"],
            ClassPostCreate(
                kind="RESOURCE",
                title="Architecture notes",
                content="Read before the next class.",
                resource_url="https://example.com/architecture-notes",
            ),
            teacher,
        )
        posts = classroom_posts(classroom["id"], student_one)
        self.assertEqual(posts[0]["title"], "Architecture notes")
        self.assertEqual(posts[0]["kind"], "RESOURCE")
        with patch("api.index.send_class_email"), patch("api.index.send_web_push"):
            recurring = create_recurring_class(
                classroom["id"],
                RecurringClassCreate(
                    weekday=date.today().weekday(),
                    starts_at=time(9),
                    ends_at=time(10),
                    topic="Weekly architecture class",
                    reminder_minutes=30,
                ),
                teacher,
            )
            recurring_session = start_recurring_class(
                recurring["id"], RecurringOccurrence(occurrence_date=recurring["next_date"]), teacher
            )
            self.assertTrue(recurring_session["id"])
            cancellation = cancel_recurring_class(
                recurring["id"],
                RecurringCancellationCreate(
                    occurrence_date=recurring["next_date"],
                    reason="Department event",
                ),
                teacher,
            )
            self.assertEqual(cancellation["notified"], 2)
            with self.assertRaises(HTTPException):
                save_attendance(
                    recurring_session["id"],
                    AttendanceUpdate(records=[AttendanceItem(student_id=student_one.id, status="PRESENT")]),
                    teacher,
                )
        class_session = create_class_session(
            classroom["id"],
            ClassSessionCreate(
                session_date=date.today(),
                starts_at=time(10),
                ends_at=time(11, 30),
                topic="Layered Architecture",
            ),
            teacher,
        )
        save_attendance(
            class_session["id"],
            AttendanceUpdate(
                records=[
                    AttendanceItem(student_id=student_one.id, status="ABSENT"),
                    AttendanceItem(student_id=student_two.id, status="PRESENT"),
                ]
            ),
            teacher,
        )
        save_attendance(
            class_session["id"],
            AttendanceUpdate(records=[AttendanceItem(student_id=student_one.id, status="PRESENT")]),
            teacher,
        )
        self.assertEqual(attendance_summary(student_one)[0]["percentage"], 100.0)
        with Session(engine) as db:
            self.assertEqual(db.scalar(select(func.count(AttendanceAudit.id))), 1)

        submit_feedback(
            classroom["id"],
            FeedbackCreate(clarity=5, organization=4, fairness=4, regularity=5, interaction=5),
            student_one,
        )
        complaint = create_complaint(
            ComplaintCreate(
                category="LAB",
                subject="Broken workstation",
                details="The workstation does not start.",
            ),
            student_one,
        )
        update_complaint(
            complaint["id"], ComplaintDecision(status="ACKNOWLEDGED"), admin
        )
        self.assertEqual(
            update_complaint(complaint["id"], ComplaintDecision(status="UNDER_REVIEW"), admin)["status"],
            "UNDER_REVIEW",
        )
        with self.assertRaises(HTTPException):
            admin_user(teacher)
        self.assertEqual(donors(blood_group="O+", batch_id=None, _=student_two)[0]["phone"], "01700000000")
        self.assertTrue(notifications(student_one))
        self.assertGreaterEqual(dashboard(admin)["students"], 2)
        self.assertEqual(dashboard(student_one)["attendance"], 100.0)
        self.assertEqual(dashboard(teacher)["classrooms"], 1)
        self.assertTrue(audit_log(admin))


if __name__ == "__main__":
    unittest.main()
