"""public application follow-up flow

Revision ID: 0004_public_application_followup
Revises: 0003_session_auth
Create Date: 2026-08-25
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_public_application_followup"
down_revision: str | None = "0003_session_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

job_role_category_enum = postgresql.ENUM("FACULTY", "NON_TEACHING", name="job_role_category", create_type=False)
intro_video_mode_enum = postgresql.ENUM("NONE", "OPTIONAL", "REQUIRED", name="intro_video_mode", create_type=False)
assessment_template_status_enum = postgresql.ENUM(
    "DRAFT", "PUBLISHED", "SUPERSEDED", name="assessment_template_status", create_type=False
)
assessment_question_type_enum = postgresql.ENUM(
    "SINGLE_CHOICE", "MULTIPLE_CHOICE", name="assessment_question_type", create_type=False
)
assessment_assignment_status_enum = postgresql.ENUM(
    "ASSIGNED", "IN_PROGRESS", "SUBMITTED", name="assessment_assignment_status", create_type=False
)
assessment_attempt_status_enum = postgresql.ENUM(
    "IN_PROGRESS", "SUBMITTED", name="assessment_attempt_status", create_type=False
)
intro_video_status_enum = postgresql.ENUM(
    "NOT_UPLOADED", "UPLOADED", "SKIPPED", name="application_intro_video_status", create_type=False
)
interview_status_enum = postgresql.ENUM(
    "NOT_SCHEDULED", "SCHEDULED", "COMPLETED", "CANCELLED", name="candidate_interview_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    job_role_category_enum.create(bind, checkfirst=True)
    intro_video_mode_enum.create(bind, checkfirst=True)
    assessment_template_status_enum.create(bind, checkfirst=True)
    assessment_question_type_enum.create(bind, checkfirst=True)
    assessment_assignment_status_enum.create(bind, checkfirst=True)
    assessment_attempt_status_enum.create(bind, checkfirst=True)
    intro_video_status_enum.create(bind, checkfirst=True)
    interview_status_enum.create(bind, checkfirst=True)

    op.execute("ALTER TYPE document_purpose ADD VALUE IF NOT EXISTS 'PHOTO'")
    op.execute("ALTER TYPE document_purpose ADD VALUE IF NOT EXISTS 'INTRO_VIDEO'")
    op.alter_column("documents", "uploaded_by_id", existing_type=sa.String(length=36), nullable=True)

    op.create_table(
        "assessment_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_assessment_templates_created_by_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_templates")),
    )
    op.create_index(op.f("ix_assessment_templates_title"), "assessment_templates", ["title"])

    op.create_table(
        "assessment_template_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", assessment_template_status_enum, nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("total_marks", sa.Float(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("published_by_id", sa.String(length=36), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["published_by_id"], ["users.id"], name=op.f("fk_assessment_template_versions_published_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["assessment_templates.id"], name=op.f("fk_assessment_template_versions_template_id_assessment_templates")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_template_versions")),
        sa.UniqueConstraint("template_id", "version_number", name="uq_assessment_template_version"),
    )
    op.create_index(
        op.f("ix_assessment_template_versions_template_id"),
        "assessment_template_versions",
        ["template_id"],
    )
    op.create_index(op.f("ix_assessment_template_versions_status"), "assessment_template_versions", ["status"])

    op.add_column(
        "jobs",
        sa.Column("role_category", job_role_category_enum, nullable=False, server_default="NON_TEACHING"),
    )
    op.add_column("jobs", sa.Column("application_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("jobs", sa.Column("intro_video_mode", intro_video_mode_enum, nullable=False, server_default="NONE"))
    op.add_column("jobs", sa.Column("assessment_template_version_id", sa.String(length=36), nullable=True))
    op.add_column("jobs", sa.Column("source_reference", sa.String(length=500), nullable=True))
    op.create_foreign_key(
        op.f("fk_jobs_assessment_template_version_id_assessment_template_versions"),
        "jobs",
        "assessment_template_versions",
        ["assessment_template_version_id"],
        ["id"],
    )
    op.create_index(op.f("ix_jobs_role_category"), "jobs", ["role_category"])
    op.create_index(op.f("ix_jobs_assessment_template_version_id"), "jobs", ["assessment_template_version_id"])

    op.add_column("applications", sa.Column("applied_designation", sa.String(length=200), nullable=True))
    op.add_column("applications", sa.Column("photo_document_id", sa.String(length=36), nullable=True))
    op.add_column(
        "applications",
        sa.Column("application_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "applications",
        sa.Column("scoring_safe_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.create_foreign_key(
        op.f("fk_applications_photo_document_id_documents"),
        "applications",
        "documents",
        ["photo_document_id"],
        ["id"],
    )
    op.create_index(op.f("ix_applications_photo_document_id"), "applications", ["photo_document_id"])

    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_version_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("question_type", assessment_question_type_enum, nullable=False),
        sa.Column("marks", sa.Float(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["assessment_template_versions.id"],
            name=op.f("fk_assessment_questions_template_version_id_assessment_template_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_questions")),
    )
    op.create_index(op.f("ix_assessment_questions_template_version_id"), "assessment_questions", ["template_version_id"])

    op.create_table(
        "assessment_options",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"], ["assessment_questions.id"], name=op.f("fk_assessment_options_question_id_assessment_questions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_options")),
    )
    op.create_index(op.f("ix_assessment_options_question_id"), "assessment_options", ["question_id"])

    op.create_table(
        "assessment_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("template_version_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", assessment_assignment_status_enum, nullable=False),
        sa.Column("version_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name=op.f("fk_assessment_assignments_application_id_applications")
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_id"], ["users.id"], name=op.f("fk_assessment_assignments_assigned_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["assessment_template_versions.id"],
            name=op.f("fk_assessment_assignments_template_version_id_assessment_template_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_assignments")),
        sa.UniqueConstraint("application_id", "template_version_id", name="uq_application_assessment"),
    )
    op.create_index(op.f("ix_assessment_assignments_application_id"), "assessment_assignments", ["application_id"])
    op.create_index(op.f("ix_assessment_assignments_status"), "assessment_assignments", ["status"])

    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("status", assessment_attempt_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name=op.f("fk_assessment_attempts_application_id_applications")
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assessment_assignments.id"], name=op.f("fk_assessment_attempts_assignment_id_assessment_assignments")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_attempts")),
    )
    op.create_index(op.f("ix_assessment_attempts_application_id"), "assessment_attempts", ["application_id"])
    op.create_index(op.f("ix_assessment_attempts_assignment_id"), "assessment_attempts", ["assignment_id"])
    op.create_index(op.f("ix_assessment_attempts_status"), "assessment_attempts", ["status"])

    op.create_table(
        "assessment_responses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("selected_option_ids", sa.JSON(), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["assessment_attempts.id"], name=op.f("fk_assessment_responses_attempt_id_assessment_attempts")
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["assessment_questions.id"], name=op.f("fk_assessment_responses_question_id_assessment_questions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_responses")),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_assessment_response"),
    )
    op.create_index(op.f("ix_assessment_responses_attempt_id"), "assessment_responses", ["attempt_id"])

    op.create_table(
        "assessment_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("achieved_marks", sa.Float(), nullable=False),
        sa.Column("total_marks", sa.Float(), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("question_breakdown", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["assessment_attempts.id"], name=op.f("fk_assessment_results_attempt_id_assessment_attempts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_results")),
        sa.UniqueConstraint("attempt_id", name=op.f("uq_assessment_results_attempt_id")),
    )

    op.create_table(
        "application_access_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exchanged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name=op.f("fk_application_access_tokens_application_id_applications")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_access_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_application_access_tokens_token_hash")),
    )
    op.create_index(op.f("ix_application_access_tokens_application_id"), "application_access_tokens", ["application_id"])
    op.create_index(op.f("ix_application_access_tokens_expires_at"), "application_access_tokens", ["expires_at"])
    op.create_index(op.f("ix_application_access_tokens_token_hash"), "application_access_tokens", ["token_hash"])

    op.create_table(
        "application_access_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent_hint", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name=op.f("fk_application_access_sessions_application_id_applications")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_access_sessions")),
        sa.UniqueConstraint("session_token_hash", name=op.f("uq_application_access_sessions_session_token_hash")),
    )
    op.create_index(op.f("ix_application_access_sessions_application_id"), "application_access_sessions", ["application_id"])
    op.create_index(op.f("ix_application_access_sessions_expires_at"), "application_access_sessions", ["expires_at"])
    op.create_index(
        op.f("ix_application_access_sessions_session_token_hash"),
        "application_access_sessions",
        ["session_token_hash"],
    )

    op.create_table(
        "application_intro_videos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("status", intro_video_status_enum, nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("storage_ref", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name=op.f("fk_application_intro_videos_application_id_applications")
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_application_intro_videos_document_id_documents")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_intro_videos")),
        sa.UniqueConstraint("application_id", name="uq_application_intro_video"),
    )
    op.create_index(op.f("ix_application_intro_videos_application_id"), "application_intro_videos", ["application_id"])
    op.create_index(op.f("ix_application_intro_videos_document_id"), "application_intro_videos", ["document_id"])

    op.create_table(
        "interview_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("status", interview_status_enum, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=True),
        sa.Column("candidate_instructions", sa.Text(), nullable=True),
        sa.Column("scheduled_by_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name=op.f("fk_interview_schedules_application_id_applications")
        ),
        sa.ForeignKeyConstraint(["scheduled_by_id"], ["users.id"], name=op.f("fk_interview_schedules_scheduled_by_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interview_schedules")),
        sa.UniqueConstraint("application_id", name="uq_application_interview_schedule"),
    )
    op.create_index(op.f("ix_interview_schedules_application_id"), "interview_schedules", ["application_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_schedules_application_id"), table_name="interview_schedules")
    op.drop_table("interview_schedules")
    op.drop_index(op.f("ix_application_intro_videos_document_id"), table_name="application_intro_videos")
    op.drop_index(op.f("ix_application_intro_videos_application_id"), table_name="application_intro_videos")
    op.drop_table("application_intro_videos")
    op.drop_index(op.f("ix_application_access_sessions_session_token_hash"), table_name="application_access_sessions")
    op.drop_index(op.f("ix_application_access_sessions_expires_at"), table_name="application_access_sessions")
    op.drop_index(op.f("ix_application_access_sessions_application_id"), table_name="application_access_sessions")
    op.drop_table("application_access_sessions")
    op.drop_index(op.f("ix_application_access_tokens_token_hash"), table_name="application_access_tokens")
    op.drop_index(op.f("ix_application_access_tokens_expires_at"), table_name="application_access_tokens")
    op.drop_index(op.f("ix_application_access_tokens_application_id"), table_name="application_access_tokens")
    op.drop_table("application_access_tokens")
    op.drop_table("assessment_results")
    op.drop_index(op.f("ix_assessment_responses_attempt_id"), table_name="assessment_responses")
    op.drop_table("assessment_responses")
    op.drop_index(op.f("ix_assessment_attempts_status"), table_name="assessment_attempts")
    op.drop_index(op.f("ix_assessment_attempts_assignment_id"), table_name="assessment_attempts")
    op.drop_index(op.f("ix_assessment_attempts_application_id"), table_name="assessment_attempts")
    op.drop_table("assessment_attempts")
    op.drop_index(op.f("ix_assessment_assignments_status"), table_name="assessment_assignments")
    op.drop_index(op.f("ix_assessment_assignments_application_id"), table_name="assessment_assignments")
    op.drop_table("assessment_assignments")
    op.drop_index(op.f("ix_assessment_options_question_id"), table_name="assessment_options")
    op.drop_table("assessment_options")
    op.drop_index(op.f("ix_assessment_questions_template_version_id"), table_name="assessment_questions")
    op.drop_table("assessment_questions")
    op.drop_index(op.f("ix_applications_photo_document_id"), table_name="applications")
    op.drop_constraint(op.f("fk_applications_photo_document_id_documents"), "applications", type_="foreignkey")
    op.drop_column("applications", "scoring_safe_payload")
    op.drop_column("applications", "application_payload")
    op.drop_column("applications", "photo_document_id")
    op.drop_column("applications", "applied_designation")
    op.drop_index(op.f("ix_jobs_assessment_template_version_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_role_category"), table_name="jobs")
    op.drop_constraint(op.f("fk_jobs_assessment_template_version_id_assessment_template_versions"), "jobs", type_="foreignkey")
    op.drop_column("jobs", "source_reference")
    op.drop_column("jobs", "assessment_template_version_id")
    op.drop_column("jobs", "intro_video_mode")
    op.drop_column("jobs", "application_config")
    op.drop_column("jobs", "role_category")
    op.drop_index(op.f("ix_assessment_template_versions_status"), table_name="assessment_template_versions")
    op.drop_index(op.f("ix_assessment_template_versions_template_id"), table_name="assessment_template_versions")
    op.drop_table("assessment_template_versions")
    op.drop_index(op.f("ix_assessment_templates_title"), table_name="assessment_templates")
    op.drop_table("assessment_templates")
    op.alter_column("documents", "uploaded_by_id", existing_type=sa.String(length=36), nullable=False)
    interview_status_enum.drop(op.get_bind(), checkfirst=True)
    intro_video_status_enum.drop(op.get_bind(), checkfirst=True)
    assessment_attempt_status_enum.drop(op.get_bind(), checkfirst=True)
    assessment_assignment_status_enum.drop(op.get_bind(), checkfirst=True)
    assessment_question_type_enum.drop(op.get_bind(), checkfirst=True)
    assessment_template_status_enum.drop(op.get_bind(), checkfirst=True)
    intro_video_mode_enum.drop(op.get_bind(), checkfirst=True)
    job_role_category_enum.drop(op.get_bind(), checkfirst=True)
