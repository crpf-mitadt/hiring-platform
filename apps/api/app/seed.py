from __future__ import annotations

# ruff: noqa: E501
import argparse
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models import (
    AssessmentOption,
    AssessmentQuestion,
    AssessmentQuestionType,
    AssessmentTemplate,
    AssessmentTemplateStatus,
    AssessmentTemplateVersion,
    Department,
    Document,
    DocumentPurpose,
    IntroVideoMode,
    Job,
    JobRoleCategory,
    JobRubric,
    JobStatus,
    Role,
    School,
    User,
    UserRole,
)
from app.services.auth import hash_password
from app.services.jobs import approve_rubric_version
from app.services.rubrics import MockRubricProvider, generate_rubric_version

DEMO_MARKER = "DEVELOPMENT / DEMO MANUAL APPROVED RUBRIC"

VACANCIES = [
    {
        "title": "Content Writer",
        "department": "Website Department",
        "designation": "Content Writer",
        "employment_type": "Full-time",
        "location": "MIT ADT University, Vishwarajbaug, Loni Kalbhor, Pune",
        "role_category": JobRoleCategory.NON_TEACHING,
        "source_reference": "https://mituniversity.ac.in/HR/vacancy_details?id=10",
        "description": (
            "Development seed based on the current public MIT-ADT Content Writer vacancy. "
            "Requires at least three years of relevant content writing experience for web, "
            "communications, and university recruitment material."
        ),
        "criteria": [
            {"criterion_id": "content_experience", "name": "Content writing experience", "category": "experience", "weight": 40},
            {"criterion_id": "web_content", "name": "Website and digital content", "category": "skill", "weight": 35},
            {"criterion_id": "editing", "name": "Editing and communication quality", "category": "skill", "weight": 25},
        ],
    },
    {
        "title": "Full Stack Developer",
        "department": "DIDU",
        "designation": "Full Stack Developer",
        "employment_type": "Full-time",
        "location": "Loni Kalbhor, Pune, Maharashtra",
        "role_category": JobRoleCategory.NON_TEACHING,
        "source_reference": "https://mituniversity.ac.in/HR/vacancy_details?id=9",
        "description": (
            "Development seed based on the current public DIDU Full Stack Developer vacancy. "
            "Targets two to three years of experience across PHP, Laravel, JavaScript, SQL, "
            "MongoDB, React, Node, Express, GitLab/GitHub, and shell scripting."
        ),
        "criteria": [
            {"criterion_id": "full_stack_experience", "name": "Full stack delivery experience", "category": "experience", "weight": 35},
            {"criterion_id": "frontend_backend", "name": "Frontend and backend skills", "category": "skill", "weight": 45},
            {"criterion_id": "version_control", "name": "Git and collaborative delivery", "category": "skill", "weight": 20},
        ],
    },
    {
        "title": "Engineering & Technology Faculty",
        "department": "Engineering & Technology Cluster",
        "designation": "Assistant Professor / Associate Professor / Professor",
        "employment_type": "Full-time",
        "location": "MIT ADT University, Vishwarajbaug, Loni Kalbhor, Pune",
        "role_category": JobRoleCategory.FACULTY,
        "source_reference": "https://mituniversity.ac.in/HR/vacancy_details?id=8",
        "description": (
            "Development seed based on the current public Engineering & Technology faculty vacancy. "
            "Uses UGC, AICTE, DG Shipping, and university norms as public eligibility references."
        ),
        "criteria": [
            {"criterion_id": "teaching", "name": "Teaching and curriculum capability", "category": "teaching", "weight": 35},
            {"criterion_id": "research", "name": "Research and publications", "category": "research", "weight": 35},
            {"criterion_id": "statutory_norms", "name": "Applicable statutory norms", "category": "eligibility", "weight": 30},
        ],
    },
    {
        "title": "Creative Cluster Faculty",
        "department": "Creative Cluster",
        "designation": "Assistant Professor / Associate Professor / Professor",
        "employment_type": "Full-time",
        "location": "MIT ADT University, Vishwarajbaug, Loni Kalbhor, Pune",
        "role_category": JobRoleCategory.FACULTY,
        "source_reference": "https://mituniversity.ac.in/HR/vacancy_details?id=7",
        "description": (
            "Development seed based on the current public Creative Cluster faculty vacancy. "
            "Uses COA, AICTE, UGC, and university norms as public eligibility references."
        ),
        "criteria": [
            {"criterion_id": "studio_teaching", "name": "Studio and classroom teaching", "category": "teaching", "weight": 35},
            {"criterion_id": "creative_research", "name": "Creative practice and research", "category": "research", "weight": 35},
            {"criterion_id": "norms", "name": "COA/AICTE/UGC norms", "category": "eligibility", "weight": 30},
        ],
    },
    {
        "title": "Management & Humanities Faculty",
        "department": "Management & Humanities Cluster",
        "designation": "Assistant Professor / Associate Professor / Professor",
        "employment_type": "Full-time",
        "location": "MIT ADT University, Vishwarajbaug, Loni Kalbhor, Pune",
        "role_category": JobRoleCategory.FACULTY,
        "source_reference": "https://mituniversity.ac.in/HR/vacancy_details?id=5",
        "description": (
            "Development seed based on the current public Management & Humanities faculty vacancy. "
            "Uses UGC 2018 plus BCI, NCTE, and AICTE public norms where applicable."
        ),
        "criteria": [
            {"criterion_id": "teaching", "name": "Teaching and academic contribution", "category": "teaching", "weight": 35},
            {"criterion_id": "research", "name": "Research and publications", "category": "research", "weight": 35},
            {"criterion_id": "regulatory", "name": "UGC/BCI/NCTE/AICTE norms", "category": "eligibility", "weight": 30},
        ],
    },
]


def seed_development_data(staff_password: str | None = None) -> None:
    if get_settings().environment not in {"development", "local"}:
        raise RuntimeError("Development seed is disabled outside development/local environments")
    password = staff_password or "change-me-development-only"
    with SessionLocal() as db:
        recruiter = _user(db, "hr.recruiter@mitadt.demo", "MIT-ADT HR Recruiter", Role.HR_RECRUITER, password)
        reviewer = _user(
            db,
            "department.reviewer@mitadt.demo",
            "MIT-ADT Department Reviewer",
            Role.DEPARTMENT_REVIEWER,
            password,
        )
        admin = _user(db, "admin@mitadt.demo", "MIT-ADT Hiring Administrator", Role.HIRING_ADMIN, password)
        _user(db, "interviewer@mitadt.demo", "MIT-ADT Interviewer", Role.INTERVIEWER, password)
        school = _school(db, "MIT Art, Design and Technology University")
        for vacancy in VACANCIES:
            department = _department(db, school, vacancy["department"])
            assessment_version = _assessment_template_version(db, admin, vacancy)
            jd_document = _document(
                db,
                recruiter,
                DocumentPurpose.JOB_JD,
                f"{vacancy['title'].lower().replace(' ', '-')}-demo-jd.txt",
                vacancy["description"].encode("utf-8"),
                "text/plain",
            )
            job = _job(db, vacancy, school, department, recruiter, reviewer, jd_document, assessment_version)
            _approved_demo_rubric(db, recruiter, job, vacancy)
        db.commit()


def reset_demo_applications() -> None:
    if get_settings().environment not in {"development", "local"}:
        raise RuntimeError("Demo reset is disabled outside development/local environments")
    with SessionLocal() as db:
        # Keep this intentionally narrow. Full destructive cleanup should stay an operator-reviewed task.
        for job in db.scalars(select(Job).where(Job.source_reference.is_not(None))):
            for application in list(job.applications) if hasattr(job, "applications") else []:
                db.delete(application)
        db.commit()


def _user(db, email: str, full_name: str, role: Role, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=full_name, password_hash=hash_password(password))
        user.roles = [UserRole(role=role)]
        db.add(user)
        db.flush()
    elif role not in {entry.role for entry in user.roles}:
        user.roles.append(UserRole(role=role))
    if user.password_hash is None:
        user.password_hash = hash_password(password)
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


def _assessment_template_version(db, actor: User, vacancy: dict) -> AssessmentTemplateVersion:
    title = f"{vacancy['title']} demo assessment"
    template = db.scalar(select(AssessmentTemplate).where(AssessmentTemplate.title == title))
    if template and template.current_version_id:
        version = db.get(AssessmentTemplateVersion, template.current_version_id)
        if version:
            return version
    if template is None:
        template = AssessmentTemplate(title=title, description="Development assessment seed data.", created_by_id=actor.id)
        db.add(template)
        db.flush()
    version = AssessmentTemplateVersion(
        template=template,
        version_number=len(template.versions) + 1,
        status=AssessmentTemplateStatus.PUBLISHED,
        title=title,
        instructions="Development assessment for product-flow testing only.",
        duration_minutes=20,
        total_marks=3,
        content={"demo": True, "source_reference": vacancy["source_reference"]},
        published_by_id=actor.id,
        published_at=utcnow(),
    )
    prompts = [
        ("Which evidence should carry the most weight for this role?", "Role-relevant experience"),
        ("Can this score automatically reject a candidate?", "No, staff review is required"),
        ("What should staff do with ambiguous evidence?", "Review the evidence manually"),
    ]
    for index, (prompt, correct) in enumerate(prompts, start=1):
        question = AssessmentQuestion(
            position=index,
            prompt=prompt,
            question_type=AssessmentQuestionType.SINGLE_CHOICE,
            marks=1,
        )
        question.options = [
            AssessmentOption(position=1, label="A", text=correct, is_correct=True),
            AssessmentOption(position=2, label="B", text="Use the AI score as the final decision", is_correct=False),
            AssessmentOption(position=3, label="C", text="Ignore submitted evidence", is_correct=False),
        ]
        version.questions.append(question)
    db.add(version)
    db.flush()
    template.current_version_id = version.id
    return version


def _job(
    db,
    vacancy: dict,
    school: School,
    department: Department,
    recruiter: User,
    reviewer: User,
    jd_document: Document,
    assessment_version: AssessmentTemplateVersion,
) -> Job:
    job = db.scalar(select(Job).where(Job.title == vacancy["title"], Job.source_reference == vacancy["source_reference"]))
    if job is None:
        job = Job(
            title=vacancy["title"],
            school_id=school.id,
            department_id=department.id,
            designation=vacancy["designation"],
            employment_type=vacancy["employment_type"],
            vacancy_count=1,
            location=vacancy["location"],
            description=vacancy["description"],
            jd_document_id=jd_document.id,
            role_category=vacancy["role_category"],
            application_config=_application_config(vacancy),
            intro_video_mode=IntroVideoMode.OPTIONAL,
            assessment_template_version_id=assessment_version.id,
            source_reference=vacancy["source_reference"],
            recruiter_id=recruiter.id,
            hiring_manager_id=reviewer.id,
            status=JobStatus.DRAFT,
        )
        job.rubrics = [JobRubric()]
        db.add(job)
        db.flush()
    else:
        job.jd_document_id = jd_document.id
        job.role_category = vacancy["role_category"]
        job.application_config = _application_config(vacancy)
        job.intro_video_mode = IntroVideoMode.OPTIONAL
        job.assessment_template_version_id = assessment_version.id
    return job


def _approved_demo_rubric(db, actor: User, job: Job, vacancy: dict) -> None:
    rubric = job.rubrics[0] if job.rubrics else JobRubric(job=job)
    if rubric.current_version_id:
        job.status = JobStatus.PUBLISHED
        return
    version = generate_rubric_version(db, actor, job, provider=MockRubricProvider())
    version.criteria = vacancy["criteria"]
    version.structured_jd_payload["demo_marker"] = DEMO_MARKER
    approve_rubric_version(db, actor, version.id)
    job.status = JobStatus.PUBLISHED


def _application_config(vacancy: dict) -> dict:
    config = {
        "source": "MIT-ADT public recruitment development seed",
        "requires_faculty_profile": vacancy["role_category"] == JobRoleCategory.FACULTY,
    }
    if vacancy["role_category"] == JobRoleCategory.FACULTY:
        config["designation_options"] = ["Assistant Professor", "Associate Professor", "Professor"]
    return config


def _document(db, actor: User, purpose: DocumentPurpose, filename: str, data: bytes, content_type: str) -> Document:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staff-password", default=None)
    parser.add_argument("--reset-demo-applications", action="store_true")
    args = parser.parse_args()
    if args.reset_demo_applications:
        reset_demo_applications()
    else:
        seed_development_data(staff_password=args.staff_password)
    print("seeded=true")


if __name__ == "__main__":
    main()
