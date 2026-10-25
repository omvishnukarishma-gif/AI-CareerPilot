"""Tests for foreign-key relationships, cascade behavior, and constraints."""

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


class TestUserRelationships:
    """Test that related records are accessible from the User model."""

    def test_user_resumes_relationship(self, db_session):
        """A user's resumes are accessible via the .resumes relationship."""
        user = User(
            email="rel@example.com",
            full_name="Rel User",
            password_hash="hash",
        )
        resume = Resume(
            user_id=None,  # will be set via relationship
            file_name="cv.pdf",
            content_text="text",
        )
        user.resumes.append(resume)
        db_session.add(user)
        db_session.commit()

        assert len(user.resumes) == 1
        assert user.resumes[0].file_name == "cv.pdf"
        assert user.resumes[0].user == user

    def test_user_job_descriptions_relationship(self, db_session):
        """A user's job descriptions are accessible via the relationship."""
        user = User(
            email="jd@example.com",
            full_name="JD User",
            password_hash="hash",
        )
        jd = JobDescription(
            user_id=None,
            title="Engineer",
            description_text="desc",
        )
        user.job_descriptions.append(jd)
        db_session.add(user)
        db_session.commit()

        assert len(user.job_descriptions) == 1
        assert user.job_descriptions[0].title == "Engineer"

    def test_user_job_applications_relationship(self, db_session):
        """A user's job applications are accessible via the relationship."""
        user = User(
            email="ja@example.com",
            full_name="JA User",
            password_hash="hash",
        )
        app = JobApplication(
            user_id=None,
            company_name="Amazon",
            role_title="L5",
        )
        user.job_applications.append(app)
        db_session.add(user)
        db_session.commit()

        assert len(user.job_applications) == 1


class TestCascadeDelete:
    """Test cascade rules when parent records are deleted."""

    def test_delete_user_cascades_to_resumes(self, db_session):
        """Deleting a user should delete all their resumes (CASCADE)."""
        user = User(
            email="cascade@example.com",
            full_name="Cascade User",
            password_hash="hash",
        )
        resume = Resume(
            user_id=None,
            file_name="resume.pdf",
            content_text="text",
        )
        user.resumes.append(resume)
        db_session.add(user)
        db_session.commit()

        resume_id = resume.id
        db_session.delete(user)
        db_session.commit()

        assert db_session.query(Resume).filter_by(id=resume_id).first() is None

    def test_delete_user_cascades_to_job_descriptions(self, db_session):
        """Deleting a user should delete all their job descriptions."""
        user = User(
            email="cd2@example.com",
            full_name="Cascade 2",
            password_hash="hash",
        )
        jd = JobDescription(
            user_id=None,
            title="Dev",
            description_text="text",
        )
        user.job_descriptions.append(jd)
        db_session.add(user)
        db_session.commit()

        jd_id = jd.id
        db_session.delete(user)
        db_session.commit()

        assert db_session.query(JobDescription).filter_by(id=jd_id).first() is None

    def test_delete_resume_cascades_to_job_matches(self, db_session):
        """Deleting a resume should cascade-delete its job_matches."""
        user = User(
            email="cd3@example.com",
            full_name="Cascade 3",
            password_hash="hash",
        )
        resume = Resume(
            user_id=None,
            file_name="r.pdf",
            content_text="text",
        )
        user.resumes.append(resume)
        db_session.add(user)
        db_session.commit()

        jd = JobDescription(
            user_id=user.id,
            title="Title",
            description_text="text",
        )
        db_session.add(jd)
        db_session.commit()

        match = JobMatch(
            resume_id=resume.id,
            job_description_id=jd.id,
            match_score=85.5,
        )
        db_session.add(match)
        db_session.commit()

        match_id = match.id
        db_session.delete(resume)
        db_session.commit()

        assert db_session.query(JobMatch).filter_by(id=match_id).first() is None

    def test_delete_interview_session_resume_sets_null(self, db_session):
        """Deleting a resume linked to an interview sets resume_id to NULL (SET NULL)."""
        user = User(
            email="cd4@example.com",
            full_name="Cascade 4",
            password_hash="hash",
        )
        resume = Resume(
            user_id=None,
            file_name="r.pdf",
            content_text="text",
        )
        user.resumes.append(resume)
        db_session.add(user)
        db_session.commit()

        session = InterviewSession(
            user_id=user.id,
            resume_id=resume.id,
            role_target="Backend Engineer",
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.id
        db_session.delete(resume)
        db_session.commit()

        retrieved = db_session.query(InterviewSession).filter_by(id=session_id).first()
        assert retrieved is not None
        assert retrieved.resume_id is None


class TestForeignKeyConstraints:
    """Test that foreign keys prevent orphan records."""

    def test_resume_requires_user_id(self, db_session):
        """A resume with a non-existent user_id should raise an error."""
        resume = Resume(
            user_id=99999,
            file_name="orphan.pdf",
            content_text="text",
        )
        db_session.add(resume)
        with pytest.raises(Exception):
            db_session.commit()

    def test_job_match_requires_resume_and_jd(self, db_session):
        """A job match needs valid resume_id and job_description_id."""
        match = JobMatch(
            resume_id=99999,
            job_description_id=88888,
            match_score=50.0,
        )
        db_session.add(match)
        with pytest.raises(Exception):
            db_session.commit()


class TestJobMatchSkillGapRelationship:
    """Test the one-to-one relationship between JobMatch and SkillGap."""

    def test_skill_gap_linked_to_job_match(self, db_session):
        """A SkillGap can be created and linked to a JobMatch."""
        user = User(
            email="sg@example.com",
            full_name="SG User",
            password_hash="hash",
        )
        resume = Resume(
            user_id=None,
            file_name="r.pdf",
            content_text="text",
        )
        user.resumes.append(resume)
        db_session.add(user)
        db_session.commit()

        jd = JobDescription(
            user_id=user.id,
            title="Title",
            description_text="text",
        )
        db_session.add(jd)
        db_session.commit()

        match = JobMatch(
            resume_id=resume.id,
            job_description_id=jd.id,
            match_score=72.0,
            matched_skills=["Python"],
            missing_skills=["Docker"],
        )
        db_session.add(match)
        db_session.commit()

        gap = SkillGap(
            job_match_id=match.id,
            resume_id=resume.id,
            job_description_id=jd.id,
            matched_skills={"matched": ["Python"]},
            missing_skills={"missing": ["Docker"]},
            recommendations={"recs": ["Learn Docker"]},
        )
        db_session.add(gap)
        db_session.commit()

        # Verify the one-to-one relationship
        assert match.skill_gap is not None
        assert match.skill_gap.job_match_id == match.id
        assert gap.job_match is match

    def test_skill_gap_unique_job_match(self, db_session):
        """Only one SkillGap per JobMatch (unique constraint)."""
        user = User(
            email="sg2@example.com",
            full_name="SG User 2",
            password_hash="hash",
        )
        resume = Resume(
            user_id=None,
            file_name="r.pdf",
            content_text="text",
        )
        user.resumes.append(resume)
        db_session.add(user)
        db_session.commit()

        jd = JobDescription(
            user_id=user.id,
            title="Title",
            description_text="text",
        )
        db_session.add(jd)
        db_session.commit()

        match = JobMatch(
            resume_id=resume.id,
            job_description_id=jd.id,
            match_score=80.0,
        )
        db_session.add(match)
        db_session.commit()

        gap1 = SkillGap(
            job_match_id=match.id,
            resume_id=resume.id,
            job_description_id=jd.id,
        )
        db_session.add(gap1)
        db_session.commit()

        gap2 = SkillGap(
            job_match_id=match.id,
            resume_id=resume.id,
            job_description_id=jd.id,
        )
        db_session.add(gap2)
        with pytest.raises(Exception):
            db_session.commit()
