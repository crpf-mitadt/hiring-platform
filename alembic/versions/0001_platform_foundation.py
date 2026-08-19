"""platform foundation

Revision ID: 0001_platform_foundation
Revises:
Create Date: 2026-08-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_platform_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

role_enum = postgresql.ENUM(
    "CANDIDATE",
    "HR_RECRUITER",
    "DEPARTMENT_REVIEWER",
    "INTERVIEWER",
    "PROCTOR",
    "HIRING_ADMIN",
    name="role",
    create_type=False,
)
job_status_enum = postgresql.ENUM("DRAFT", "PUBLISHED", "CLOSED", name="job_status", create_type=False)
application_stage_enum = postgresql.ENUM(
    "APPLICATION_RECEIVED",
    "SCREENING_PENDING",
    "SCREENING_RUNNING",
    "SCREENING_COMPLETE",
    "SCREENING_REVIEW",
    "SHORTLISTED_FOR_ASSESSMENT",
    "SCREENING_HOLD",
    "NOT_PROGRESSED_AFTER_SCREENING",
    name="application_stage",
    create_type=False,
)
hiring_decision_enum = postgresql.ENUM(
    "SELECTED",
    "NOT_SELECTED",
    "HOLD",
    "ANOTHER_ROUND",
    name="hiring_decision_type",
    create_type=False,
)
screening_run_status_enum = postgresql.ENUM(
    "QUEUED",
    "RUNNING",
    "COMPLETE",
    "FAILED",
    name="screening_run_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    role_enum.create(bind, checkfirst=True)
    job_status_enum.create(bind, checkfirst=True)
    application_stage_enum.create(bind, checkfirst=True)
    hiring_decision_enum.create(bind, checkfirst=True)
    screening_run_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"])

    op.create_table(
        "schools",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schools")),
        sa.UniqueConstraint("name", name=op.f("uq_schools_name")),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
    )
    op.create_index(op.f("ix_user_roles_role"), "user_roles", ["role"])
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"])

    op.create_table(
        "departments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], name=op.f("fk_departments_school_id_schools")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
    )
    op.create_index(op.f("ix_departments_name"), "departments", ["name"])
    op.create_index(op.f("ix_departments_school_id"), "departments", ["school_id"])

    op.create_table(
        "candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("education_profile", sa.JSON(), nullable=False),
        sa.Column("work_experience_profile", sa.JSON(), nullable=False),
        sa.Column("resume_document_ref", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_candidates_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
        sa.UniqueConstraint("user_id", name=op.f("uq_candidates_user_id")),
    )
    op.create_index(op.f("ix_candidates_email"), "candidates", ["email"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("department_id", sa.String(length=36), nullable=False),
        sa.Column("designation", sa.String(length=200), nullable=False),
        sa.Column("employment_type", sa.String(length=80), nullable=False),
        sa.Column("vacancy_count", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("application_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("application_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("jd_document_ref", sa.String(length=500), nullable=True),
        sa.Column("recruiter_id", sa.String(length=36), nullable=False),
        sa.Column("hiring_manager_id", sa.String(length=36), nullable=False),
        sa.Column("status", job_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], name=op.f("fk_jobs_department_id_departments")
        ),
        sa.ForeignKeyConstraint(["hiring_manager_id"], ["users.id"], name=op.f("fk_jobs_hiring_manager_id_users")),
        sa.ForeignKeyConstraint(["recruiter_id"], ["users.id"], name=op.f("fk_jobs_recruiter_id_users")),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], name=op.f("fk_jobs_school_id_schools")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index(op.f("ix_jobs_department_id"), "jobs", ["department_id"])
    op.create_index(op.f("ix_jobs_hiring_manager_id"), "jobs", ["hiring_manager_id"])
    op.create_index(op.f("ix_jobs_recruiter_id"), "jobs", ["recruiter_id"])
    op.create_index(op.f("ix_jobs_school_id"), "jobs", ["school_id"])
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"])
    op.create_index(op.f("ix_jobs_title"), "jobs", ["title"])

    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resume_document_ref", sa.String(length=500), nullable=True),
        sa.Column("current_stage", application_stage_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"], name=op.f("fk_applications_candidate_id_candidates")
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_applications_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job_application"),
    )
    op.create_index(op.f("ix_applications_candidate_id"), "applications", ["candidate_id"])
    op.create_index(op.f("ix_applications_current_stage"), "applications", ["current_stage"])
    op.create_index(op.f("ix_applications_job_id"), "applications", ["job_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_audit_events_actor_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"])
    op.create_index(op.f("ix_audit_events_actor_id"), "audit_events", ["actor_id"])
    op.create_index(op.f("ix_audit_events_entity_id"), "audit_events", ["entity_id"])
    op.create_index(op.f("ix_audit_events_entity_type"), "audit_events", ["entity_type"])

    op.create_table(
        "application_stage_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("previous_stage", application_stage_enum, nullable=True),
        sa.Column("new_stage", application_stage_enum, nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_application_stage_history_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_application_stage_history_application_id_applications"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_stage_history")),
    )
    op.create_index(
        op.f("ix_application_stage_history_actor_id"), "application_stage_history", ["actor_id"]
    )
    op.create_index(
        op.f("ix_application_stage_history_application_id"),
        "application_stage_history",
        ["application_id"],
    )

    op.create_table(
        "hiring_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("decision", hiring_decision_enum, nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_hiring_decisions_actor_id_users")),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name=op.f("fk_hiring_decisions_application_id_applications")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hiring_decisions")),
    )
    op.create_index(op.f("ix_hiring_decisions_actor_id"), "hiring_decisions", ["actor_id"])
    op.create_index(op.f("ix_hiring_decisions_application_id"), "hiring_decisions", ["application_id"])

    op.create_table(
        "job_reviewers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_reviewers_job_id_jobs")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_job_reviewers_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_reviewers")),
        sa.UniqueConstraint("job_id", "user_id", name="uq_job_reviewers_job_user"),
    )
    op.create_index(op.f("ix_job_reviewers_job_id"), "job_reviewers", ["job_id"])
    op.create_index(op.f("ix_job_reviewers_user_id"), "job_reviewers", ["user_id"])

    op.create_table(
        "job_rubrics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_rubrics_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_rubrics")),
    )
    op.create_index(op.f("ix_job_rubrics_job_id"), "job_rubrics", ["job_id"])

    op.create_table(
        "job_rubric_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rubric_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("proposed_by", sa.String(length=30), nullable=False),
        sa.Column("approved_by_id", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("engine_mapping", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by_id"], ["users.id"], name=op.f("fk_job_rubric_versions_approved_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["rubric_id"], ["job_rubrics.id"], name=op.f("fk_job_rubric_versions_rubric_id_job_rubrics")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_rubric_versions")),
        sa.UniqueConstraint("rubric_id", "version_number", name="uq_rubric_version"),
    )
    op.create_index(op.f("ix_job_rubric_versions_rubric_id"), "job_rubric_versions", ["rubric_id"])

    op.create_table(
        "screening_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("rubric_version_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_engine_version", sa.String(length=100), nullable=False),
        sa.Column("run_status", screening_run_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligibility", sa.String(length=30), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("evidence_completeness", sa.Float(), nullable=True),
        sa.Column("confirmed_experience_months", sa.Integer(), nullable=True),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("raw_result_ref", sa.String(length=500), nullable=True),
        sa.Column("raw_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name=op.f("fk_screening_runs_application_id_applications")
        ),
        sa.ForeignKeyConstraint(
            ["rubric_version_id"],
            ["job_rubric_versions.id"],
            name=op.f("fk_screening_runs_rubric_version_id_job_rubric_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_runs")),
    )
    op.create_index(op.f("ix_screening_runs_application_id"), "screening_runs", ["application_id"])
    op.create_index(op.f("ix_screening_runs_rubric_version_id"), "screening_runs", ["rubric_version_id"])
    op.create_index(op.f("ix_screening_runs_run_status"), "screening_runs", ["run_status"])

    op.create_table(
        "screening_criterion_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("screening_run_id", sa.String(length=36), nullable=False),
        sa.Column("criterion_id", sa.String(length=120), nullable=False),
        sa.Column("criterion_name", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("match_fraction", sa.Float(), nullable=False),
        sa.Column("weighted_score", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("missing_information", sa.JSON(), nullable=False),
        sa.Column("raw_component_assessment", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["screening_run_id"],
            ["screening_runs.id"],
            name=op.f("fk_screening_criterion_results_screening_run_id_screening_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_criterion_results")),
    )
    op.create_index(
        op.f("ix_screening_criterion_results_criterion_id"),
        "screening_criterion_results",
        ["criterion_id"],
    )
    op.create_index(
        op.f("ix_screening_criterion_results_screening_run_id"),
        "screening_criterion_results",
        ["screening_run_id"],
    )

    op.create_table(
        "screening_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("criterion_result_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_document_id", sa.String(length=200), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("block_index", sa.Integer(), nullable=True),
        sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("evidence_status", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["criterion_result_id"],
            ["screening_criterion_results.id"],
            name=op.f("fk_screening_evidence_criterion_result_id_screening_criterion_results"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_evidence")),
    )
    op.create_index(
        op.f("ix_screening_evidence_criterion_result_id"), "screening_evidence", ["criterion_result_id"]
    )


def downgrade() -> None:
    op.drop_table("screening_evidence")
    op.drop_table("screening_criterion_results")
    op.drop_table("screening_runs")
    op.drop_table("job_rubric_versions")
    op.drop_table("job_rubrics")
    op.drop_table("job_reviewers")
    op.drop_table("hiring_decisions")
    op.drop_table("application_stage_history")
    op.drop_table("audit_events")
    op.drop_table("applications")
    op.drop_table("jobs")
    op.drop_table("candidates")
    op.drop_table("departments")
    op.drop_table("user_roles")
    op.drop_table("schools")
    op.drop_table("users")

    bind = op.get_bind()
    screening_run_status_enum.drop(bind, checkfirst=True)
    hiring_decision_enum.drop(bind, checkfirst=True)
    application_stage_enum.drop(bind, checkfirst=True)
    job_status_enum.drop(bind, checkfirst=True)
    role_enum.drop(bind, checkfirst=True)
