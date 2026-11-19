"""screening integration foundation

Revision ID: 0002_screening_integration
Revises: 0001_platform_foundation
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_screening_integration"
down_revision: str | None = "0001_platform_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

document_purpose_enum = postgresql.ENUM("JOB_JD", "RESUME", name="document_purpose", create_type=False)
rubric_version_status_enum = postgresql.ENUM(
    "DRAFT",
    "PROPOSED",
    "APPROVED",
    "SUPERSEDED",
    name="rubric_version_status",
    create_type=False,
)
screening_job_status_enum = postgresql.ENUM(
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    name="screening_job_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    document_purpose_enum.create(bind, checkfirst=True)
    rubric_version_status_enum.create(bind, checkfirst=True)
    screening_job_status_enum.create(bind, checkfirst=True)

    op.execute("ALTER TYPE screening_run_status ADD VALUE IF NOT EXISTS 'PENDING'")
    op.execute("ALTER TYPE screening_run_status ADD VALUE IF NOT EXISTS 'COMPLETED'")

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("purpose", document_purpose_enum, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], name=op.f("fk_documents_uploaded_by_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_documents_storage_key")),
    )
    op.create_index(op.f("ix_documents_purpose"), "documents", ["purpose"])
    op.create_index(op.f("ix_documents_sha256"), "documents", ["sha256"])
    op.create_index(op.f("ix_documents_uploaded_by_id"), "documents", ["uploaded_by_id"])

    op.add_column("jobs", sa.Column("jd_document_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(op.f("fk_jobs_jd_document_id_documents"), "jobs", "documents", ["jd_document_id"], ["id"])
    op.create_index(op.f("ix_jobs_jd_document_id"), "jobs", ["jd_document_id"])

    op.add_column("candidates", sa.Column("resume_document_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        op.f("fk_candidates_resume_document_id_documents"),
        "candidates",
        "documents",
        ["resume_document_id"],
        ["id"],
    )
    op.create_index(op.f("ix_candidates_resume_document_id"), "candidates", ["resume_document_id"])

    op.add_column("applications", sa.Column("resume_document_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        op.f("fk_applications_resume_document_id_documents"),
        "applications",
        "documents",
        ["resume_document_id"],
        ["id"],
    )
    op.create_index(op.f("ix_applications_resume_document_id"), "applications", ["resume_document_id"])

    op.alter_column(
        "job_rubric_versions",
        "status",
        existing_type=sa.String(length=30),
        type_=rubric_version_status_enum,
        postgresql_using="UPPER(status)::rubric_version_status",
        existing_nullable=False,
    )
    op.create_index(op.f("ix_job_rubric_versions_status"), "job_rubric_versions", ["status"])
    op.add_column("job_rubric_versions", sa.Column("source_jd_document_id", sa.String(length=36), nullable=True))
    op.add_column("job_rubric_versions", sa.Column("source_jd_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "job_rubric_versions",
        sa.Column("source_structured_jd_schema_version", sa.String(length=60), nullable=True),
    )
    op.add_column(
        "job_rubric_versions",
        sa.Column("structured_jd_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column("job_rubric_versions", sa.Column("approved_payload_sha256", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        op.f("fk_job_rubric_versions_source_jd_document_id_documents"),
        "job_rubric_versions",
        "documents",
        ["source_jd_document_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_job_rubric_versions_source_jd_document_id"),
        "job_rubric_versions",
        ["source_jd_document_id"],
    )
    op.create_index(
        op.f("ix_job_rubric_versions_approved_payload_sha256"),
        "job_rubric_versions",
        ["approved_payload_sha256"],
    )

    op.add_column("screening_runs", sa.Column("retry_of_run_id", sa.String(length=36), nullable=True))
    op.add_column("screening_runs", sa.Column("jd_document_id", sa.String(length=36), nullable=True))
    op.add_column("screening_runs", sa.Column("jd_document_sha256", sa.String(length=64), nullable=True))
    op.add_column("screening_runs", sa.Column("resume_document_id", sa.String(length=36), nullable=True))
    op.add_column("screening_runs", sa.Column("resume_document_sha256", sa.String(length=64), nullable=True))
    op.add_column("screening_runs", sa.Column("engine_contract_version", sa.String(length=80), nullable=True))
    op.add_column("screening_runs", sa.Column("engine_artifact_schema_version", sa.String(length=80), nullable=True))
    op.add_column("screening_runs", sa.Column("engine_code_version", sa.String(length=120), nullable=True))
    op.add_column("screening_runs", sa.Column("model_endpoint_slot", sa.String(length=30), nullable=True))
    op.add_column("screening_runs", sa.Column("structured_jd_sha256", sa.String(length=64), nullable=True))
    op.add_column("screening_runs", sa.Column("structured_resume_sha256", sa.String(length=64), nullable=True))
    op.add_column("screening_runs", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("screening_runs", sa.Column("failure_code", sa.String(length=120), nullable=True))
    op.add_column("screening_runs", sa.Column("failure_message", sa.Text(), nullable=True))
    op.add_column(
        "screening_runs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("screening_runs", sa.Column("score_before_gates", sa.Float(), nullable=True))
    op.add_column("screening_runs", sa.Column("maximum_score", sa.Float(), nullable=True))
    op.add_column(
        "screening_runs",
        sa.Column("uncertain_experience_ranges", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "screening_runs",
        sa.Column("mandatory_requirement_results", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column("screening_runs", sa.Column("human_review_required", sa.Boolean(), nullable=True))
    op.add_column("screening_runs", sa.Column("recommendation_label", sa.String(length=100), nullable=True))
    op.create_foreign_key(
        op.f("fk_screening_runs_retry_of_run_id_screening_runs"),
        "screening_runs",
        "screening_runs",
        ["retry_of_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_screening_runs_jd_document_id_documents"),
        "screening_runs",
        "documents",
        ["jd_document_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_screening_runs_resume_document_id_documents"),
        "screening_runs",
        "documents",
        ["resume_document_id"],
        ["id"],
    )
    op.create_index(op.f("ix_screening_runs_retry_of_run_id"), "screening_runs", ["retry_of_run_id"])
    op.create_index(op.f("ix_screening_runs_jd_document_id"), "screening_runs", ["jd_document_id"])
    op.create_index(op.f("ix_screening_runs_resume_document_id"), "screening_runs", ["resume_document_id"])

    op.add_column("screening_criterion_results", sa.Column("weight", sa.Float(), nullable=True))
    op.add_column(
        "screening_criterion_results",
        sa.Column("requirement_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "screening_criterion_results",
        sa.Column("candidate_requirement", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "screening_criterion_results",
        sa.Column("evidence_found", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "screening_criterion_results",
        sa.Column("ambiguity", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "screening_criterion_results",
        sa.Column("verification_needed", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "screening_criterion_results",
        sa.Column("matched_terms", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "screening_criterion_results",
        sa.Column("unmatched_terms", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )

    op.create_table(
        "screening_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("screening_run_id", sa.String(length=36), nullable=False),
        sa.Column("status", screening_job_status_enum, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["screening_run_id"],
            ["screening_runs.id"],
            name=op.f("fk_screening_jobs_screening_run_id_screening_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_jobs")),
        sa.UniqueConstraint("screening_run_id", name=op.f("uq_screening_jobs_screening_run_id")),
    )
    op.create_index(op.f("ix_screening_jobs_status"), "screening_jobs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_screening_jobs_status"), table_name="screening_jobs")
    op.drop_table("screening_jobs")

    for column_name in (
        "unmatched_terms",
        "matched_terms",
        "verification_needed",
        "ambiguity",
        "evidence_found",
        "candidate_requirement",
        "requirement_ids",
        "weight",
    ):
        op.drop_column("screening_criterion_results", column_name)

    op.drop_index(op.f("ix_screening_runs_resume_document_id"), table_name="screening_runs")
    op.drop_index(op.f("ix_screening_runs_jd_document_id"), table_name="screening_runs")
    op.drop_index(op.f("ix_screening_runs_retry_of_run_id"), table_name="screening_runs")
    op.drop_constraint(op.f("fk_screening_runs_resume_document_id_documents"), "screening_runs", type_="foreignkey")
    op.drop_constraint(op.f("fk_screening_runs_jd_document_id_documents"), "screening_runs", type_="foreignkey")
    op.drop_constraint(op.f("fk_screening_runs_retry_of_run_id_screening_runs"), "screening_runs", type_="foreignkey")
    for column_name in (
        "recommendation_label",
        "human_review_required",
        "mandatory_requirement_results",
        "uncertain_experience_ranges",
        "maximum_score",
        "score_before_gates",
        "attempt_count",
        "failure_message",
        "failure_code",
        "failed_at",
        "structured_resume_sha256",
        "structured_jd_sha256",
        "model_endpoint_slot",
        "engine_code_version",
        "engine_artifact_schema_version",
        "engine_contract_version",
        "resume_document_sha256",
        "resume_document_id",
        "jd_document_sha256",
        "jd_document_id",
        "retry_of_run_id",
    ):
        op.drop_column("screening_runs", column_name)

    op.drop_index(op.f("ix_job_rubric_versions_approved_payload_sha256"), table_name="job_rubric_versions")
    op.drop_index(op.f("ix_job_rubric_versions_source_jd_document_id"), table_name="job_rubric_versions")
    op.drop_constraint(
        op.f("fk_job_rubric_versions_source_jd_document_id_documents"),
        "job_rubric_versions",
        type_="foreignkey",
    )
    for column_name in (
        "approved_payload_sha256",
        "structured_jd_payload",
        "source_structured_jd_schema_version",
        "source_jd_sha256",
        "source_jd_document_id",
    ):
        op.drop_column("job_rubric_versions", column_name)
    op.drop_index(op.f("ix_job_rubric_versions_status"), table_name="job_rubric_versions")
    op.alter_column(
        "job_rubric_versions",
        "status",
        existing_type=rubric_version_status_enum,
        type_=sa.String(length=30),
        postgresql_using="LOWER(status::text)",
        existing_nullable=False,
    )

    op.drop_index(op.f("ix_applications_resume_document_id"), table_name="applications")
    op.drop_constraint(op.f("fk_applications_resume_document_id_documents"), "applications", type_="foreignkey")
    op.drop_column("applications", "resume_document_id")

    op.drop_index(op.f("ix_candidates_resume_document_id"), table_name="candidates")
    op.drop_constraint(op.f("fk_candidates_resume_document_id_documents"), "candidates", type_="foreignkey")
    op.drop_column("candidates", "resume_document_id")

    op.drop_index(op.f("ix_jobs_jd_document_id"), table_name="jobs")
    op.drop_constraint(op.f("fk_jobs_jd_document_id_documents"), "jobs", type_="foreignkey")
    op.drop_column("jobs", "jd_document_id")

    op.drop_index(op.f("ix_documents_uploaded_by_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_sha256"), table_name="documents")
    op.drop_index(op.f("ix_documents_purpose"), table_name="documents")
    op.drop_table("documents")

    bind = op.get_bind()
    screening_job_status_enum.drop(bind, checkfirst=True)
    rubric_version_status_enum.drop(bind, checkfirst=True)
    document_purpose_enum.drop(bind, checkfirst=True)
