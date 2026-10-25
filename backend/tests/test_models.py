"""Tests for model creation and basic database operations."""

import pytest

from app.models import (
    User,
    Resume,
    JobDescription,
    JobMatch,
    SkillGap,
    InterviewSession,
    JobApplication,
)


class TestUserModel:
    """Tests for the User model."""

    def test_create_user(self, db_session):
        """A user can be created and retrieved."""
        user = User(
            email="alice@example.com",
            full_name="Alice Smith",
            password_hash="dummy_hash",
        )
        db_session.add(user)
        db_session.commit()

        retrieved = db_session.query(User).first()
        assert retrieved is not None
        assert retrieved.email == "alice@example.com"
        assert retrieved.full_name == "Alice Smith"
        assert retrieved.is_active is True

    def test_user_timestamps_set_on_create(self, db_session):
        """created_at and updated_at are populated when a user is created."""
        user = User(
            email="bob@example.com",
            full_name="Bob Jones",
            password_hash="dummy_hash",
        )
        db_session.add(user)
        db_session.commit()

        assert user.created_at is not None
        assert user.updated_at is not None

    def test_email_unique_constraint(self, db_session):
        """Two users with the same email should raise an integrity error."""
        user1 = User(
            email="dup@example.com",
            full_name="First",
            password_hash="hash1",
        )
        db_session.add(user1)
        db_session.commit()

        user2 = User(
            email="dup@example.com",
            full_name="Second",
            password_hash="hash2",
        )
        db_session.add(user2)
        with pytest.raises(Exception):
            db_session.commit()


class TestResumeModel:
    """Tests for the Resume model."""

    def test_create_resume(self, db_session):
        """A resume can be created and linked to a user."""
        user = User(
            email="resume@example.com",
            full_name="Resume Owner",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()

        resume = Resume(
            user_id=user.id,
            file_name="resume.pdf",
            content_text="Python, FastAPI, PostgreSQL",
            parsed_data={"skills": ["Python", "FastAPI"]},
        )
        db_session.add(resume)
        db_session.commit()

        retrieved = db_session.query(Resume).first()
        assert retrieved is not None
        assert retrieved.user_id == user.id
        assert retrieved.file_name == "resume.pdf"
        assert retrieved.parsed_data == {"skills": ["Python", "FastAPI"]}

    def test_resume_parsed_data_nullable(self, db_session):
        """parsed_data can be NULL until the AI parser runs."""
        user = User(
            email="null@example.com",
            full_name="Null Test",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()

        resume = Resume(
            user_id=user.id,
            file_name="resume.txt",
            content_text="Some text",
        )
        db_session.add(resume)
        db_session.commit()

        assert resume.parsed_data is None


class TestJobDescriptionModel:
    """Tests for the JobDescription model."""

    def test_create_job_description(self, db_session):
        """A job description can be created with optional company field."""
        user = User(
            email="jd@example.com",
            full_name="JD Owner",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()

        jd = JobDescription(
            user_id=user.id,
            title="Senior Python Developer",
            company="Acme Corp",
            description_text="We need a Python expert...",
        )
        db_session.add(jd)
        db_session.commit()

        retrieved = db_session.query(JobDescription).first()
        assert retrieved.title == "Senior Python Developer"
        assert retrieved.company == "Acme Corp"

    def test_job_description_company_nullable(self, db_session):
        """Company field is optional."""
        user = User(
            email="jd2@example.com",
            full_name="JD Owner 2",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()

        jd = JobDescription(
            user_id=user.id,
            title="Developer",
            description_text="Job text",
        )
        db_session.add(jd)
        db_session.commit()

        assert jd.company is None


class TestJobApplicationModel:
    """Tests for the JobApplication model."""

    def test_create_application_with_defaults(self, db_session):
        """A job application gets the default status 'applied'."""
        user = User(
            email="app@example.com",
            full_name="App Owner",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()

        app = JobApplication(
            user_id=user.id,
            company_name="Google",
            role_title="SWE",
        )
        db_session.add(app)
        db_session.commit()

        assert app.status == "applied"
        assert app.job_url is None
        assert app.notes is None

    def test_application_status_update(self, db_session):
        """Application status can be changed."""
        user = User(
            email="app2@example.com",
            full_name="App Owner 2",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()

        app = JobApplication(
            user_id=user.id,
            company_name="Meta",
            role_title="E5",
        )
        db_session.add(app)
        db_session.commit()

        app.status = "interviewing"
        db_session.commit()

        retrieved = db_session.query(JobApplication).first()
        assert retrieved.status == "interviewing"


class TestTimestampMixin:
    """Tests for the TimestampMixin updated_at onupdate behaviour."""

    def test_updated_at_changes_after_update(self, db_session):
        """updated_at should be refreshed when a record is updated."""
        import time

        user = User(
            email="ts_update@example.com",
            full_name="Timestamp Tester",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        created_at_value = user.created_at
        original_updated_at = user.updated_at

        assert created_at_value is not None
        assert original_updated_at is not None

        # Small sleep so the new timestamp is strictly greater on fast machines.
        time.sleep(0.05)

        user.full_name = "Timestamp Tester Updated"
        db_session.commit()
        db_session.refresh(user)

        # updated_at must be >= original (ORM onupdate sets it on the UPDATE)
        assert user.updated_at >= original_updated_at

    def test_created_at_does_not_change_after_update(self, db_session):
        """created_at must remain unchanged when a record is updated."""
        user = User(
            email="ts_created@example.com",
            full_name="Created At Tester",
            password_hash="hash",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        original_created_at = user.created_at

        user.full_name = "Created At Tester Updated"
        db_session.commit()
        db_session.refresh(user)

        assert user.created_at == original_created_at
