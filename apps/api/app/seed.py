from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models import (
    Candidate,
    Department,
    Document,
    DocumentPurpose,
    Job,
    JobReviewer,
    JobRubric,
    JobStatus,
    Role,
    School,
    User,
    UserRole,
)
from app.schemas.applications import ApplicationCreate, CandidateCreate
from app.services.applications import submit_application
from app.services.jobs import approve_rubric_version
from app.services.rubrics import MockRubricProvider, generate_rubric_version
from app.services.screening import MockScreeningProvider, enqueue_screening_run, process_next_screening_job


def seed_development_data() -> None:
    with SessionLocal() as db:
        recruiter = _user(db, "recruiter@example.org", "Synthetic Recruiter", Role.HR_RECRUITER)
        reviewer = _user(db, "reviewer@example.org", "Synthetic Reviewer", Role.DEPARTMENT_REVIEWER)
        candidate_user = _user(db, "candidate@example.org", "Synthetic Candidate", Role.CANDIDATE)
        school = _school(db, "Synthetic School")
        department = _department(db, school, "Synthetic Computer Science")
        jd_document = _document(
            db,
            recruiter,
            DocumentPurpose.JOB_JD,
            "synthetic-assistant-professor-jd.txt",
            b"Synthetic JD requiring teaching, Python, mentoring, and evidence-backed experience.",
            "text/plain",
        )
        resume_document = _document(
            db,
            candidate_user,
            DocumentPurpose.RESUME,
            "synthetic-candidate-profile.json",
            b'{"candidate_id":"synthetic-candidate","schema_version":"structured-resume-v1"}',
            "application/json",
        )
        job = db.scalar(select(Job).where(Job.title == "Assistant Professor - Synthetic Seed"))
        if job is None:
            job = Job(
                title="Assistant Professor - Synthetic Seed",
                school_id=school.id,
                department_id=department.id,
                designation="Assistant Professor",
                employment_type="Full Time",
                vacancy_count=2,
                location="Pune",
                description="Synthetic seed role for local screening integration development.",
                jd_document_id=jd_document.id,
                recruiter_id=recruiter.id,
                hiring_manager_id=reviewer.id,
                status=JobStatus.DRAFT,
            )
            job.reviewers = [JobReviewer(user_id=reviewer.id)]
            job.rubrics = [JobRubric()]
            db.add(job)
            db.flush()
        if not job.rubrics[0].current_version_id:
            version = generate_rubric_version(db, recruiter, job, provider=MockRubricProvider())
            approve_rubric_version(db, recruiter, version.id)
        job.status = JobStatus.PUBLISHED

        candidate = db.scalar(select(Candidate).where(Candidate.user_id == candidate_user.id))
        if candidate is None:
            application = submit_application(
                db,
                candidate_user,
                job.id,
                ApplicationCreate(
                    candidate=CandidateCreate(
                        user_id=candidate_user.id,
                        full_name=candidate_user.full_name,
                        email=candidate_user.email,
                        phone="0000000000",
                        education_profile={"highest_degree": "Synthetic postgraduate degree"},
                        work_experience_profile={"summary": "Synthetic teaching and programming experience"},
                        resume_document_id=resume_document.id,
                    ),
                    resume_document_id=resume_document.id,
                ),
            )
            enqueue_screening_run(db, application_id=application.id, actor=recruiter)
            process_next_screening_job(db, provider=MockScreeningProvider())
        db.commit()


def _user(db, email: str, full_name: str, role: Role) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=full_name)
        user.roles = [UserRole(role=role)]
        db.add(user)
        db.flush()
    elif role not in {entry.role for entry in user.roles}:
        user.roles.append(UserRole(role=role))
    return user


def _school(db, name: str) -> School:
    school = db.scalar(select(School).where(School.name == name))
    if school is None:
        school = School(name=name)
        db.add(school)
        db.flush()
    return school


def _department(db, school: School, name: str) -> Department:
    department = db.scalar(select(Department).where(Department.school_id == school.id, Department.name == name))
    if department is None:
        department = Department(school_id=school.id, name=name)
        db.add(department)
        db.flush()
    return department


def _document(
    db,
    actor: User,
    purpose: DocumentPurpose,
    filename: str,
    data: bytes,
    content_type: str,
) -> Document:
    digest = sha256(data).hexdigest()
    document = db.scalar(select(Document).where(Document.sha256 == digest, Document.original_filename == filename))
    if document is not None:
        return document
    storage_key = f"{purpose.value}/{filename}"
    root = Path(get_settings().document_storage_root).expanduser().resolve()
    path = root / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    document = Document(
        purpose=purpose,
        original_filename=filename,
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=len(data),
        sha256=digest,
        uploaded_by_id=actor.id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(document)
    db.flush()
    return document


if __name__ == "__main__":
    seed_development_data()
    print("seeded=true")
