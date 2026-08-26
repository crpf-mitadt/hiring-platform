from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
from hashlib import sha256
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models import (
    Application,
    ApplicationAccessSession,
    ApplicationAccessToken,
    ApplicationIntroVideo,
    ApplicationStageHistory,
    AssessmentAssignment,
    AssessmentAttempt,
    AssessmentOption,
    AssessmentQuestion,
    AssessmentQuestionType,
    AssessmentResponse,
    AssessmentResult,
    AssessmentTemplate,
    AssessmentTemplateStatus,
    AssessmentTemplateVersion,
    AuditEvent,
    Department,
    Document,
    DocumentPurpose,
    HiringDecision,
    InterviewSchedule,
    IntroVideoMode,
    Job,
    JobRoleCategory,
    JobRubric,
    JobRubricVersion,
    JobStatus,
    Role,
    RubricVersionStatus,
    School,
    ScreeningCriterionResult,
    ScreeningEvidence,
    ScreeningJob,
    ScreeningRun,
    User,
    UserRole,
)
from app.services.auth import hash_password
from app.services.jobs import approve_rubric_version
from app.services.rubric_utils import rubric_payload_hash

DEMO_MARKER = "DEVELOPMENT / DEMO MANUAL APPROVED RUBRIC"
DEMO_STRUCTURED_JD_REVISION = "mit-adt-demo-structured-jd-v2"
DEMO_RUBRIC_PROVIDER = "development-seed-manual-approved"

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

DEMO_STRUCTURED_JD_PROFILES = {
    "Content Writer": {
        "domain": "Website and university communications content",
        "seniority": "Experienced",
        "minimum_experience_months": 36,
        "role_summary": (
            "Content Writer for university website, landing pages, blogs, news, brochures, campaigns, "
            "and promotional material with strong English writing, editing, SEO, and CMS skills."
        ),
        "responsibilities": [
            "Write original and well-structured content for websites, landing pages, blogs, news, brochures, campaign pages, and promotional material.",
            "Edit, proofread, and refine copy for grammar, clarity, tone, factual consistency, and university communication standards.",
            "Create SEO-aware content using keyword research, on-page content optimization, and web-content best practices.",
            "Research academic, technical, and institutional subjects and simplify them for public and applicant-facing audiences.",
            "Use a CMS, preferably WordPress, and AI-assisted content tools responsibly while preserving originality.",
        ],
        "mandatory_requirements": [
            "Minimum three years of relevant content writing experience.",
            "Excellent written English communication.",
            "Experience writing, editing, proofreading, and copywriting for web or institutional communication.",
        ],
        "preferred_requirements": [
            "SEO content, keyword research, on-page content optimization, and digital marketing familiarity.",
            "CMS experience, preferably WordPress.",
            "Ability to simplify technical or academic material without losing accuracy.",
        ],
        "required_skills": [
            "Content writing",
            "Editing",
            "Proofreading",
            "Copywriting",
            "Written English communication",
            "Web content",
            "SEO content",
        ],
        "preferred_skills": [
            "Keyword research",
            "On-page content optimization",
            "CMS",
            "WordPress",
            "Digital marketing content",
            "UX writing",
            "AI-assisted content tools",
        ],
        "adjacent_skills": ["Research", "Academic content simplification", "Technical content simplification"],
        "criterion_details": {
            "content_experience": {
                "description": "Evidence of at least three years of relevant content writing, copywriting, editing, or institutional communication experience.",
                "mandatory": True,
                "required_skill_names": ["Content writing", "Copywriting", "Written English communication"],
                "preferred_skill_names": ["Digital marketing content", "AI-assisted content tools"],
                "adjacent_skill_names": ["Research"],
                "evaluation_dimensions": ["relevant content experience", "original structured writing", "institutional tone"],
                "requirement_ids": ["minimum-content-experience", "written-english"],
            },
            "web_content": {
                "description": "Evidence of web-first content work, SEO awareness, keyword research, CMS/WordPress usage, and landing-page or campaign content.",
                "mandatory": True,
                "required_skill_names": ["Web content", "SEO content"],
                "preferred_skill_names": ["Keyword research", "On-page content optimization", "CMS", "WordPress", "UX writing"],
                "adjacent_skill_names": ["Technical content simplification", "Academic content simplification"],
                "evaluation_dimensions": ["website content", "SEO and keyword use", "CMS workflow"],
                "requirement_ids": ["web-content", "seo-content", "cms"],
            },
            "editing": {
                "description": "Evidence of proofreading, editing, clarity, grammar, and ability to simplify complex academic or technical information.",
                "mandatory": True,
                "required_skill_names": ["Editing", "Proofreading", "Written English communication"],
                "preferred_skill_names": ["Technical content simplification", "Academic content simplification"],
                "adjacent_skill_names": ["Research"],
                "evaluation_dimensions": ["language quality", "accuracy", "clarity"],
                "requirement_ids": ["editing", "proofreading", "simplification"],
            },
        },
    },
    "Full Stack Developer": {
        "domain": "Full-stack web and application development",
        "seniority": "2-3 years",
        "minimum_experience_months": 24,
        "maximum_experience_months": 36,
        "role_summary": (
            "Full Stack Developer for DIDU website and application work across PHP, Laravel, WordPress, JavaScript, "
            "HTML, CSS, SQL/MySQL, MongoDB, React.js, Node.js, Express, GitLab/GitHub, bash scripting, testing, "
            "debugging, performance, security, and basic DevOps collaboration."
        ),
        "responsibilities": [
            "Maintain and develop university websites, landing pages, and application features.",
            "Build and support PHP, Laravel, and WordPress projects with reliable server-side behavior.",
            "Deliver frontend interfaces using JavaScript, HTML, CSS, React.js where relevant, and UI/UX implementation discipline.",
            "Work with SQL/MySQL and MongoDB data stores and support database-backed application features.",
            "Use GitLab/GitHub for version control, collaboration, review, and coordinated delivery.",
            "Support server-side operations, bash scripting, unit testing, bug fixing, performance, security, and basic DevOps or CI/CD activities.",
        ],
        "mandatory_requirements": [
            "Two to three years of relevant full-stack development experience.",
            "Practical frontend and backend delivery experience.",
            "Version-control and collaborative software delivery experience using GitLab or GitHub.",
        ],
        "preferred_requirements": [
            "PHP, Laravel, WordPress, JavaScript, HTML, CSS, SQL/MySQL, MongoDB, React.js, Node.js, and Express experience.",
            "Bash scripting, server-side operations, testing, debugging, performance, security, and basic DevOps exposure.",
            "Website maintenance, landing-page delivery, analytics/SEO awareness, and clear communication.",
        ],
        "required_skills": [
            "PHP",
            "Laravel",
            "JavaScript",
            "HTML",
            "CSS",
            "SQL",
            "MySQL",
            "Full-stack development",
            "Frontend development",
            "Backend development",
            "GitLab",
            "GitHub",
        ],
        "preferred_skills": [
            "WordPress",
            "MongoDB",
            "React.js",
            "Node.js",
            "Express",
            "Bash scripting",
            "Unit testing",
            "Debugging",
            "Performance optimization",
            "Security practices",
            "Basic DevOps",
        ],
        "adjacent_skills": ["Java", "Server-side operations", "CI/CD", "SEO", "Analytics", "UI/UX implementation"],
        "criterion_details": {
            "full_stack_experience": {
                "description": "Evidence of two to three years of full-stack delivery across frontend, backend, website, application, database, and server-side work.",
                "mandatory": True,
                "required_skill_names": ["Full-stack development", "Frontend development", "Backend development"],
                "preferred_skill_names": ["Website maintenance", "Application development", "Server-side operations"],
                "adjacent_skill_names": ["UI/UX implementation", "SEO", "Analytics"],
                "evaluation_dimensions": ["confirmed relevant months", "frontend/backend delivery", "website and application delivery"],
                "requirement_ids": ["full-stack-experience", "frontend-backend-delivery"],
            },
            "frontend_backend": {
                "description": "Evidence of role-specific frontend, backend, CMS, database, testing, debugging, performance, security, and basic DevOps skills.",
                "mandatory": True,
                "required_skill_names": ["PHP", "Laravel", "JavaScript", "HTML", "CSS", "SQL", "MySQL"],
                "preferred_skill_names": ["WordPress", "MongoDB", "React.js", "Node.js", "Express", "Bash scripting", "Unit testing", "Debugging", "Performance optimization", "Security practices", "Basic DevOps"],
                "adjacent_skill_names": ["Java", "Server-side operations", "CI/CD"],
                "evaluation_dimensions": ["backend stack", "frontend stack", "database work", "testing and debugging", "operations awareness"],
                "requirement_ids": ["php-laravel", "frontend-stack", "database-stack", "testing-debugging"],
            },
            "version_control": {
                "description": "Evidence of GitLab or GitHub usage, collaborative delivery, review discipline, and ownership in software work.",
                "mandatory": True,
                "required_skill_names": ["GitLab", "GitHub"],
                "preferred_skill_names": ["Collaboration", "Code review", "Ownership"],
                "adjacent_skill_names": ["CI/CD"],
                "evaluation_dimensions": ["version control", "collaboration", "delivery ownership"],
                "requirement_ids": ["gitlab-github", "collaborative-delivery"],
            },
        },
    },
    "Engineering & Technology Faculty": {
        "domain": "Engineering and technology faculty",
        "seniority": "As per UGC/AICTE/DG Shipping/University norms",
        "minimum_experience_months": 0,
        "role_summary": "Teaching faculty role aligned to engineering and technology academic norms, research, mentoring, assessment, and institutional contribution.",
        "responsibilities": [
            "Prepare instruction plans and deliver regular classes using appropriate ICT and pedagogy.",
            "Maintain academic standards through tutorials, assessment, mentoring, dissertation guidance, and examination duties.",
            "Publish research papers, pursue research projects, and participate in conferences, workshops, and committees.",
            "Meet applicable UGC, AICTE, DG Shipping, and university eligibility norms.",
        ],
        "mandatory_requirements": [
            "Teaching and curriculum capability for engineering or technology subjects.",
            "Eligibility as per UGC, AICTE, DG Shipping, and university norms where applicable.",
        ],
        "preferred_requirements": ["Research publications", "Research projects", "ICT-enabled teaching", "Mentoring and dissertation guidance"],
        "required_skills": ["Teaching", "Curriculum delivery", "Academic assessment", "Student mentoring"],
        "preferred_skills": ["Research publications", "Research projects", "ICT teaching", "Conference participation"],
        "adjacent_skills": ["Committee contribution", "Dissertation guidance", "Workshop participation"],
        "criterion_details": {
            "teaching": {
                "description": "Evidence of teaching, instructional planning, curriculum delivery, mentoring, tutorials, and assessment capability.",
                "mandatory": True,
                "required_skill_names": ["Teaching", "Curriculum delivery", "Academic assessment", "Student mentoring"],
                "preferred_skill_names": ["ICT teaching", "Dissertation guidance"],
                "adjacent_skill_names": ["Workshop participation"],
                "evaluation_dimensions": ["teaching capability", "student-facing academic delivery", "assessment and mentoring"],
                "requirement_ids": ["engineering-teaching", "academic-assessment"],
            },
            "research": {
                "description": "Evidence of research publications, projects, academic journals, conferences, and scholarly contribution.",
                "mandatory": True,
                "required_skill_names": ["Research publications"],
                "preferred_skill_names": ["Research projects", "Conference participation"],
                "adjacent_skill_names": ["Academic journals", "Workshop participation"],
                "evaluation_dimensions": ["publication record", "research activity", "academic contribution"],
                "requirement_ids": ["engineering-research", "publications"],
            },
            "statutory_norms": {
                "description": "Evidence of eligibility under UGC, AICTE, DG Shipping, and university norms for engineering and technology roles.",
                "mandatory": True,
                "required_skill_names": ["UGC norms", "AICTE norms", "University norms"],
                "preferred_skill_names": ["DG Shipping norms"],
                "adjacent_skill_names": [],
                "evaluation_dimensions": ["statutory eligibility", "role-specific qualifications"],
                "requirement_ids": ["ugc-aicte-dg-shipping-norms"],
            },
        },
    },
    "Creative Cluster Faculty": {
        "domain": "Creative cluster faculty",
        "seniority": "As per COA/AICTE/UGC/University norms",
        "minimum_experience_months": 0,
        "role_summary": "Creative cluster teaching faculty role aligned to studio/classroom teaching, creative practice, research, mentoring, assessment, and statutory norms.",
        "responsibilities": [
            "Deliver studio and classroom teaching with clear instructional plans and academic standards.",
            "Support tutorials, assessment, mentoring, dissertation or project guidance, and examination duties.",
            "Contribute through creative practice, research publications, projects, conferences, workshops, and committees.",
            "Meet applicable COA, AICTE, UGC, and university eligibility norms.",
        ],
        "mandatory_requirements": [
            "Studio or classroom teaching capability in a creative discipline.",
            "Eligibility as per COA, AICTE, UGC, and university norms where applicable.",
        ],
        "preferred_requirements": ["Creative practice", "Research publications", "ICT-enabled teaching", "Mentoring and project guidance"],
        "required_skills": ["Studio teaching", "Classroom teaching", "Creative practice", "Academic assessment", "Student mentoring"],
        "preferred_skills": ["Research publications", "Research projects", "ICT teaching", "Conference participation"],
        "adjacent_skills": ["Committee contribution", "Project guidance", "Workshop participation"],
        "criterion_details": {
            "studio_teaching": {
                "description": "Evidence of studio and classroom teaching, instructional planning, student-facing delivery, mentoring, and assessment.",
                "mandatory": True,
                "required_skill_names": ["Studio teaching", "Classroom teaching", "Academic assessment", "Student mentoring"],
                "preferred_skill_names": ["ICT teaching", "Project guidance"],
                "adjacent_skill_names": ["Workshop participation"],
                "evaluation_dimensions": ["studio teaching", "classroom delivery", "student-facing mentoring"],
                "requirement_ids": ["creative-teaching", "studio-delivery"],
            },
            "creative_research": {
                "description": "Evidence of creative practice, research, publications, projects, conferences, and academic contribution.",
                "mandatory": True,
                "required_skill_names": ["Creative practice", "Research publications"],
                "preferred_skill_names": ["Research projects", "Conference participation"],
                "adjacent_skill_names": ["Academic journals", "Workshop participation"],
                "evaluation_dimensions": ["creative practice", "research activity", "academic contribution"],
                "requirement_ids": ["creative-research", "publications"],
            },
            "norms": {
                "description": "Evidence of eligibility under COA, AICTE, UGC, and university norms for creative cluster roles.",
                "mandatory": True,
                "required_skill_names": ["COA norms", "AICTE norms", "UGC norms", "University norms"],
                "preferred_skill_names": [],
                "adjacent_skill_names": [],
                "evaluation_dimensions": ["statutory eligibility", "role-specific qualifications"],
                "requirement_ids": ["coa-aicte-ugc-norms"],
            },
        },
    },
    "Management & Humanities Faculty": {
        "domain": "Management and humanities faculty",
        "seniority": "As per UGC 2018 and applicable statutory norms",
        "minimum_experience_months": 0,
        "role_summary": "Management and humanities teaching faculty role aligned to UGC 2018 and applicable BCI, NCTE, AICTE, university norms, teaching, research, mentoring, and academic governance.",
        "responsibilities": [
            "Deliver regular classes with instruction plans, tutorials, mentoring, dissertation guidance, assessment, and examination duties.",
            "Maintain academic standards and contribute to curriculum, committees, workshops, and institutional academic work.",
            "Publish research papers, pursue research projects, and participate in conferences and scholarly activities.",
            "Meet UGC 2018 and applicable BCI, NCTE, AICTE, and university eligibility norms.",
        ],
        "mandatory_requirements": [
            "Teaching and academic contribution capability for management or humanities subjects.",
            "Eligibility as per UGC 2018 and applicable BCI, NCTE, AICTE, and university norms.",
        ],
        "preferred_requirements": ["Research publications", "Research projects", "ICT-enabled teaching", "Mentoring and dissertation guidance"],
        "required_skills": ["Teaching", "Academic contribution", "Curriculum delivery", "Academic assessment", "Student mentoring"],
        "preferred_skills": ["Research publications", "Research projects", "ICT teaching", "Conference participation"],
        "adjacent_skills": ["Committee contribution", "Dissertation guidance", "Workshop participation"],
        "criterion_details": {
            "teaching": {
                "description": "Evidence of teaching, academic contribution, curriculum delivery, mentoring, dissertation guidance, tutorials, and assessment.",
                "mandatory": True,
                "required_skill_names": ["Teaching", "Academic contribution", "Curriculum delivery", "Academic assessment", "Student mentoring"],
                "preferred_skill_names": ["ICT teaching", "Dissertation guidance"],
                "adjacent_skill_names": ["Committee contribution"],
                "evaluation_dimensions": ["teaching capability", "student-facing academic delivery", "assessment and mentoring"],
                "requirement_ids": ["management-humanities-teaching", "academic-contribution"],
            },
            "research": {
                "description": "Evidence of research publications, projects, academic journals, conferences, and scholarly contribution.",
                "mandatory": True,
                "required_skill_names": ["Research publications"],
                "preferred_skill_names": ["Research projects", "Conference participation"],
                "adjacent_skill_names": ["Academic journals", "Workshop participation"],
                "evaluation_dimensions": ["publication record", "research activity", "academic contribution"],
                "requirement_ids": ["management-humanities-research", "publications"],
            },
            "regulatory": {
                "description": "Evidence of eligibility under UGC 2018 plus applicable BCI, NCTE, AICTE, and university norms.",
                "mandatory": True,
                "required_skill_names": ["UGC 2018 norms", "University norms"],
                "preferred_skill_names": ["BCI norms", "NCTE norms", "AICTE norms"],
                "adjacent_skill_names": [],
                "evaluation_dimensions": ["statutory eligibility", "role-specific qualifications"],
                "requirement_ids": ["ugc-2018-bci-ncte-aicte-norms"],
            },
        },
    },
}


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
        source_references = {vacancy["source_reference"] for vacancy in VACANCIES}
        demo_job_ids = list(
            db.scalars(select(Job.id).where(Job.source_reference.in_(source_references)))
        )
        if not demo_job_ids:
            return
        application_ids = list(
            db.scalars(select(Application.id).where(Application.job_id.in_(demo_job_ids)))
        )
        if not application_ids:
            return
        screening_run_ids = list(
            db.scalars(select(ScreeningRun.id).where(ScreeningRun.application_id.in_(application_ids)))
        )
        criterion_result_ids = (
            list(
                db.scalars(
                    select(ScreeningCriterionResult.id).where(
                        ScreeningCriterionResult.screening_run_id.in_(screening_run_ids)
                    )
                )
            )
            if screening_run_ids
            else []
        )
        assessment_assignment_ids = list(
            db.scalars(select(AssessmentAssignment.id).where(AssessmentAssignment.application_id.in_(application_ids)))
        )
        assessment_attempt_ids = list(
            db.scalars(select(AssessmentAttempt.id).where(AssessmentAttempt.application_id.in_(application_ids)))
        )
        intro_video_ids = list(
            db.scalars(select(ApplicationIntroVideo.id).where(ApplicationIntroVideo.application_id.in_(application_ids)))
        )
        interview_schedule_ids = list(
            db.scalars(select(InterviewSchedule.id).where(InterviewSchedule.application_id.in_(application_ids)))
        )
        _delete_demo_application_dependents(
            db,
            application_ids=application_ids,
            screening_run_ids=screening_run_ids,
            criterion_result_ids=criterion_result_ids,
            assessment_assignment_ids=assessment_assignment_ids,
            assessment_attempt_ids=assessment_attempt_ids,
            intro_video_ids=intro_video_ids,
            interview_schedule_ids=interview_schedule_ids,
        )
        db.execute(delete(Application).where(Application.id.in_(application_ids)))
        db.commit()


def _delete_demo_application_dependents(
    db,
    *,
    application_ids: list[str],
    screening_run_ids: list[str],
    criterion_result_ids: list[str],
    assessment_assignment_ids: list[str],
    assessment_attempt_ids: list[str],
    intro_video_ids: list[str],
    interview_schedule_ids: list[str],
) -> None:
    if criterion_result_ids:
        db.execute(delete(ScreeningEvidence).where(ScreeningEvidence.criterion_result_id.in_(criterion_result_ids)))
    if screening_run_ids:
        db.execute(delete(ScreeningCriterionResult).where(ScreeningCriterionResult.screening_run_id.in_(screening_run_ids)))
        db.execute(delete(ScreeningJob).where(ScreeningJob.screening_run_id.in_(screening_run_ids)))
    if assessment_attempt_ids:
        db.execute(delete(AssessmentResult).where(AssessmentResult.attempt_id.in_(assessment_attempt_ids)))
        db.execute(delete(AssessmentResponse).where(AssessmentResponse.attempt_id.in_(assessment_attempt_ids)))
        db.execute(delete(AssessmentAttempt).where(AssessmentAttempt.id.in_(assessment_attempt_ids)))
    if assessment_assignment_ids:
        db.execute(delete(AssessmentAssignment).where(AssessmentAssignment.id.in_(assessment_assignment_ids)))
    db.execute(delete(ApplicationAccessSession).where(ApplicationAccessSession.application_id.in_(application_ids)))
    db.execute(delete(ApplicationAccessToken).where(ApplicationAccessToken.application_id.in_(application_ids)))
    db.execute(delete(ApplicationStageHistory).where(ApplicationStageHistory.application_id.in_(application_ids)))
    db.execute(delete(HiringDecision).where(HiringDecision.application_id.in_(application_ids)))
    db.execute(delete(ApplicationIntroVideo).where(ApplicationIntroVideo.application_id.in_(application_ids)))
    db.execute(delete(InterviewSchedule).where(InterviewSchedule.application_id.in_(application_ids)))
    if screening_run_ids:
        db.execute(delete(ScreeningRun).where(ScreeningRun.id.in_(screening_run_ids)))
    _delete_demo_audit_events(
        db,
        application_ids=application_ids,
        screening_run_ids=screening_run_ids,
        assessment_assignment_ids=assessment_assignment_ids,
        assessment_attempt_ids=assessment_attempt_ids,
        intro_video_ids=intro_video_ids,
        interview_schedule_ids=interview_schedule_ids,
    )


def _delete_demo_audit_events(
    db,
    *,
    application_ids: list[str],
    screening_run_ids: list[str],
    assessment_assignment_ids: list[str],
    assessment_attempt_ids: list[str],
    intro_video_ids: list[str],
    interview_schedule_ids: list[str],
) -> None:
    audit_scopes = [
        ("application", application_ids),
        ("screening_run", screening_run_ids),
        ("assessment_assignment", assessment_assignment_ids),
        ("assessment_attempt", assessment_attempt_ids),
        ("application_intro_video", intro_video_ids),
        ("interview_schedule", interview_schedule_ids),
    ]
    for entity_type, entity_ids in audit_scopes:
        if entity_ids:
            db.execute(
                delete(AuditEvent).where(
                    AuditEvent.entity_type == entity_type,
                    AuditEvent.entity_id.in_(entity_ids),
                )
            )


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
    if rubric not in job.rubrics:
        db.add(rubric)
        db.flush()
    payload = _structured_jd_payload(job, vacancy)
    criteria = payload["scoring_rubric"]
    _validate_demo_rubric_payload(job, vacancy, payload, criteria)
    current_version = db.get(JobRubricVersion, rubric.current_version_id) if rubric.current_version_id else None
    if _is_current_corrected_seed_version(current_version, payload, criteria):
        job.status = JobStatus.PUBLISHED
        return
    for version in rubric.versions:
        if _is_current_corrected_seed_version(version, payload, criteria):
            rubric.current_version_id = version.id
            job.status = JobStatus.PUBLISHED
            return
    version = JobRubricVersion(
        rubric=rubric,
        version_number=max((entry.version_number for entry in rubric.versions), default=0) + 1,
        status=RubricVersionStatus.DRAFT,
        proposed_by=DEMO_RUBRIC_PROVIDER,
        source_jd_document_id=job.jd_document_id,
        source_jd_sha256=job.jd_document.sha256 if job.jd_document else None,
        source_structured_jd_schema_version=payload["schema_version"],
        structured_jd_payload=payload,
        criteria=criteria,
        engine_mapping={
            "contract_version": "platform-rubric-provider-v1",
            "source": DEMO_RUBRIC_PROVIDER,
            "engine_schema": "StructuredJD",
            "seed_revision": DEMO_STRUCTURED_JD_REVISION,
            "seed_fingerprint": payload["seed_fingerprint"],
            "approval_note": DEMO_MARKER,
        },
    )
    db.add(version)
    db.flush()
    approve_rubric_version(db, actor, version.id)
    job.status = JobStatus.PUBLISHED


def _is_current_corrected_seed_version(
    version: JobRubricVersion | None,
    payload: dict,
    criteria: list[dict],
) -> bool:
    if version is None or version.status != RubricVersionStatus.APPROVED:
        return False
    if version.proposed_by != DEMO_RUBRIC_PROVIDER:
        return False
    if version.structured_jd_payload != payload or version.criteria != criteria:
        return False
    return version.approved_payload_sha256 == rubric_payload_hash(version)


def _structured_jd_payload(job: Job, vacancy: dict) -> dict:
    profile = DEMO_STRUCTURED_JD_PROFILES[vacancy["title"]]
    criteria = _criteria_for_vacancy(vacancy, profile)
    return {
        "schema_version": "structured-jd-v1",
        "seed_revision": DEMO_STRUCTURED_JD_REVISION,
        "seed_fingerprint": _seed_fingerprint(vacancy),
        "demo_marker": DEMO_MARKER,
        "job_id": job.id,
        "source_reference": vacancy["source_reference"],
        "source_document_id": job.jd_document.id if job.jd_document else job.jd_document_ref or "manual-jd",
        "source_document_sha256": job.jd_document.sha256 if job.jd_document else None,
        "extraction_method": "development_manual_seed",
        "job_title": vacancy["title"],
        "department": vacancy["department"],
        "designation": vacancy["designation"],
        "employment_type": vacancy["employment_type"],
        "location": vacancy["location"],
        "role_category": vacancy["role_category"].value,
        "role_summary": profile["role_summary"],
        "responsibilities": profile["responsibilities"],
        "mandatory_requirements": profile["mandatory_requirements"],
        "preferred_requirements": profile["preferred_requirements"],
        "required_skills": profile["required_skills"],
        "preferred_skills": profile["preferred_skills"],
        "adjacent_skills": profile["adjacent_skills"],
        "minimum_experience_months": profile["minimum_experience_months"],
        "maximum_experience_months": profile.get("maximum_experience_months"),
        "domain": profile["domain"],
        "seniority": profile["seniority"],
        "contains_teaching": vacancy["role_category"] == JobRoleCategory.FACULTY,
        "contains_student_facing": vacancy["role_category"] == JobRoleCategory.FACULTY,
        "scoring_rubric": criteria,
        "extraction_warnings": [DEMO_MARKER],
    }


def _criteria_for_vacancy(vacancy: dict, profile: dict) -> list[dict]:
    criteria = []
    for base in vacancy["criteria"]:
        details = profile["criterion_details"][base["criterion_id"]]
        criteria.append({**base, **details})
    return criteria


def _seed_fingerprint(vacancy: dict) -> str:
    payload = {
        "revision": DEMO_STRUCTURED_JD_REVISION,
        "source_reference": vacancy["source_reference"],
        "title": vacancy["title"],
        "criteria": vacancy["criteria"],
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"{DEMO_STRUCTURED_JD_REVISION}:{digest}"


def _validate_demo_rubric_payload(job: Job, vacancy: dict, payload: dict, criteria: list[dict]) -> None:
    if payload["job_id"] != job.id:
        raise RuntimeError(f"Demo StructuredJD job_id mismatch for {vacancy['title']}")
    if payload["job_title"] != vacancy["title"] or payload["department"] != vacancy["department"]:
        raise RuntimeError(f"Demo StructuredJD vacancy identity mismatch for {vacancy['title']}")
    if criteria != payload["scoring_rubric"]:
        raise RuntimeError(f"Demo criteria diverged from StructuredJD scoring_rubric for {vacancy['title']}")
    expected_by_id = {criterion["criterion_id"]: criterion for criterion in vacancy["criteria"]}
    actual_by_id = {criterion["criterion_id"]: criterion for criterion in criteria}
    if set(actual_by_id) != set(expected_by_id):
        raise RuntimeError(f"Demo criterion IDs diverged from vacancy seed for {vacancy['title']}")
    for criterion_id, expected in expected_by_id.items():
        actual = actual_by_id[criterion_id]
        for field in ("name", "category", "weight"):
            if actual[field] != expected[field]:
                raise RuntimeError(f"Demo criterion {criterion_id} {field} mismatch for {vacancy['title']}")
    if vacancy["role_category"] == JobRoleCategory.NON_TEACHING:
        blocked_terms = ["teaching", "student-facing", "student facing", "academic journal", "research papers"]
        text = _payload_text(payload)
        for term in blocked_terms:
            if term in text:
                raise RuntimeError(f"Non-teaching demo StructuredJD contains faculty-only term '{term}' for {vacancy['title']}")
    if vacancy["title"] == "Full Stack Developer" and "research" in _payload_text(payload):
        raise RuntimeError("Full Stack Developer demo StructuredJD must not contain research requirements")


def _payload_text(payload: dict) -> str:
    excluded_keys = {
        "contains_student_facing",
        "contains_teaching",
        "demo_marker",
        "extraction_warnings",
        "role_category",
    }
    values: list[str] = []

    def collect(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key not in excluded_keys:
                    collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)
        elif isinstance(value, str):
            values.append(value)

    collect(payload)
    return json.dumps(values, sort_keys=True).lower()


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
