"""Reset user-owned data and seed development accounts.

Run from ``backend`` with::

    ./.venv/bin/python seed_test_users.py --reset-users
"""

import argparse
import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from api.index import (
    CRAppointment,
    CRCandidate,
    CRElection,
    CRPosition,
    StudentProfile,
    User,
    classify_email,
    engine,
    ensure_student_batch,
    hash_password,
)

PASSWORD = "12345678"


def seed() -> list[tuple[str, str, str]]:
    super_admin_email = os.environ.get("SUPER_ADMIN_EMAIL", "").strip().lower()
    if not super_admin_email:
        raise RuntimeError("SUPER_ADMIN_EMAIL must be configured before seeding")

    accounts = [
        ("Super Admin", super_admin_email, "SUPER_ADMIN", "ACTIVE"),
        ("Department Admin", "department.admin@iit.du.ac.bd", "DEPARTMENT_ADMIN", "ACTIVE"),
        ("Active Teacher", "teacher@iit.du.ac.bd", "TEACHER", "ACTIVE"),
        ("Pending Teacher", "pending.teacher@iit.du.ac.bd", "TEACHER", "PENDING"),
    ]
    student_accounts = [
        ("Batch 15 Student 1", "bsse1501@iit.du.ac.bd", "STUDENT", "ACTIVE"),
        ("Batch 15 Student 2", "bsse1502@iit.du.ac.bd", "STUDENT", "ACTIVE"),
        ("Batch 18 Student", "bsse1805@iit.du.ac.bd", "STUDENT", "ACTIVE"),
        ("Batch 18 Student 2", "bsse1806@iit.du.ac.bd", "STUDENT", "ACTIVE"),
    ]
    accounts.extend(account for account in student_accounts if account[1] != super_admin_email)

    password_hash = hash_password(PASSWORD)
    with Session(engine) as db:
        # User is the root of the user-owned foreign-key graph. CASCADE removes
        # profiles, elections, appointments, classrooms, attendance and messages.
        db.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))

        users: dict[str, User] = {}
        for name, email, role, status in accounts:
            user = User(
                name=name,
                email=email,
                password_hash=password_hash,
                role=role,
                status=status,
            )
            db.add(user)
            db.flush()
            users[email] = user
            if role == "STUDENT":
                _, _, identity = classify_email(email)
                batch = ensure_student_batch(db, identity)
                db.add(StudentProfile(user_id=user.id, batch_id=batch.id, **identity))

        cr_email = "bsse1501@iit.du.ac.bd"
        if users[cr_email].role != "STUDENT":
            cr_email = "bsse1502@iit.du.ac.bd"
        cr = users[cr_email]
        profile = db.get(StudentProfile, cr.id)
        position = db.scalar(
            select(CRPosition).where(
                CRPosition.batch_id == profile.batch_id,
                CRPosition.title == "Seeded General CR",
            )
        )
        if not position:
            position = CRPosition(batch_id=profile.batch_id, title="Seeded General CR", seats=1)
            db.add(position)
            db.flush()

        now = datetime.now(timezone.utc)
        election = CRElection(
            position_id=position.id,
            title="Seeded CR Appointment",
            nomination_start=now - timedelta(days=8),
            nomination_end=now - timedelta(days=7),
            voting_start=now - timedelta(days=6),
            voting_end=now - timedelta(days=5),
            status="CLOSED",
            created_by=users[super_admin_email].id,
        )
        db.add(election)
        db.flush()
        db.add(CRCandidate(election_id=election.id, student_id=cr.id, manifesto="Seeded CR", status="APPROVED"))
        db.add(
            CRAppointment(
                election_id=election.id,
                position_id=position.id,
                student_id=cr.id,
                start_date=date.today(),
                status="ACTIVE",
            )
        )
        db.commit()

    return [(email, role, status) for _, email, role, status in accounts]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset-users",
        action="store_true",
        help="confirm deletion of all existing users and dependent records",
    )
    args = parser.parse_args()
    if not args.reset_users:
        parser.error("--reset-users is required because this operation is destructive")
    seeded = seed()
    print(f"Seeded {len(seeded)} accounts. Shared password: {PASSWORD}")
    for email, role, status in seeded:
        print(f"{email}\t{role}\t{status}")
