"""bulk screening

Revision ID: 0005_bulk_screening
Revises: 0004_public_application_followup
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_bulk_screening"
down_revision: str | None = "0004_public_application_followup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_type_enum = postgresql.ENUM("EXISTING_JOB", "ADHOC_JD", name="bulk_screening_source_type", create_type=False)
batch_status_enum = postgresql.ENUM(
    "DRAFT", "READY", "QUEUED", "RUNNING", "COMPLETED", "FAILED", name="bulk_screening_batch_status", create_type=False
)
item_status_enum = postgresql.ENUM(
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "DUPLICATE",
    "UNSUPPORTED",
    name="bulk_screening_item_status",
    create_type=False,
)
classification_enum = postgresql.ENUM(
    "MEETS_CRITERIA",
    "DOES_NOT_MEET_CRITERIA",
    "NEEDS_REVIEW",
    name="bulk_screening_classification",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    source_type_enum.create(bind, checkfirst=True)
    batch_status_enum.create(bind, checkfirst=True)
    item_status_enum.create(bind, checkfirst=True)
    classification_enum.create(bind, checkfirst=True)

    op.create_table(
        "bulk_screening_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_by_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("rubric_version_id", sa.String(length=36), nullable=True),
        sa.Column("ad_hoc_jd_document_id", sa.String(length=36), nullable=True),
        sa.Column("ad_hoc_structured_jd", sa.JSON(), nullable=True),
        sa.Column("ad_hoc_structured_jd_sha256", sa.String(length=64), nullable=True),
        sa.Column("criteria_snapshot", sa.JSON(), nullable=False),
        sa.Column("criteria_confirmed_by_id", sa.String(length=36), nullable=True),
        sa.Column("criteria_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", batch_status_enum, nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("unsupported_count", sa.Integer(), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ad_hoc_jd_document_id"],
            ["documents.id"],
            name=op.f("fk_bulk_screening_batches_ad_hoc_jd_document_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_bulk_screening_batches_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["criteria_confirmed_by_id"],
            ["users.id"],
            name=op.f("fk_bulk_screening_batches_criteria_confirmed_by_id_users"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_bulk_screening_batches_job_id_jobs")),
        sa.ForeignKeyConstraint(
            ["rubric_version_id"],
            ["job_rubric_versions.id"],
            name=op.f("fk_bulk_screening_batches_rubric_version_id_job_rubric_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bulk_screening_batches")),
    )
    op.create_index(op.f("ix_bulk_screening_batches_created_by_id"), "bulk_screening_batches", ["created_by_id"])
    op.create_index(op.f("ix_bulk_screening_batches_source_type"), "bulk_screening_batches", ["source_type"])
    op.create_index(op.f("ix_bulk_screening_batches_job_id"), "bulk_screening_batches", ["job_id"])
    op.create_index(
        op.f("ix_bulk_screening_batches_rubric_version_id"), "bulk_screening_batches", ["rubric_version_id"]
    )
    op.create_index(
        op.f("ix_bulk_screening_batches_ad_hoc_jd_document_id"), "bulk_screening_batches", ["ad_hoc_jd_document_id"]
    )
    op.create_index(op.f("ix_bulk_screening_batches_status"), "bulk_screening_batches", ["status"])

    op.create_table(
        "bulk_screening_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("resume_document_id", sa.String(length=36), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("duplicate_of_item_id", sa.String(length=36), nullable=True),
        sa.Column("status", item_status_enum, nullable=False),
        sa.Column("classification", classification_enum, nullable=True),
        sa.Column("concise_reason", sa.Text(), nullable=True),
        sa.Column("candidate_name", sa.String(length=240), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("provider_engine_version", sa.String(length=100), nullable=True),
        sa.Column("engine_contract_version", sa.String(length=80), nullable=True),
        sa.Column("engine_artifact_schema_version", sa.String(length=80), nullable=True),
        sa.Column("engine_code_version", sa.String(length=120), nullable=True),
        sa.Column("model_endpoint_slot", sa.String(length=30), nullable=True),
        sa.Column("eligibility", sa.String(length=30), nullable=True),
        sa.Column("evidence_completeness", sa.Float(), nullable=True),
        sa.Column("confirmed_experience_months", sa.Integer(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("raw_result_ref", sa.String(length=500), nullable=True),
        sa.Column("raw_result", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["bulk_screening_batches.id"],
            name=op.f("fk_bulk_screening_items_batch_id_bulk_screening_batches"),
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_item_id"],
            ["bulk_screening_items.id"],
            name=op.f("fk_bulk_screening_items_duplicate_of_item_id_bulk_screening_items"),
        ),
        sa.ForeignKeyConstraint(
            ["resume_document_id"], ["documents.id"], name=op.f("fk_bulk_screening_items_resume_document_id_documents")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bulk_screening_items")),
    )
    op.create_index(op.f("ix_bulk_screening_items_batch_id"), "bulk_screening_items", ["batch_id"])
    op.create_index(op.f("ix_bulk_screening_items_resume_document_id"), "bulk_screening_items", ["resume_document_id"])
    op.create_index(op.f("ix_bulk_screening_items_content_sha256"), "bulk_screening_items", ["content_sha256"])
    op.create_index(
        op.f("ix_bulk_screening_items_duplicate_of_item_id"), "bulk_screening_items", ["duplicate_of_item_id"]
    )
    op.create_index(op.f("ix_bulk_screening_items_status"), "bulk_screening_items", ["status"])
    op.create_index(op.f("ix_bulk_screening_items_classification"), "bulk_screening_items", ["classification"])

    op.create_table(
        "bulk_screening_criterion_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("criterion_id", sa.String(length=120), nullable=False),
        sa.Column("criterion_name", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("candidate_requirement", sa.Text(), nullable=False),
        sa.Column("evidence_found", sa.JSON(), nullable=False),
        sa.Column("missing_information", sa.JSON(), nullable=False),
        sa.Column("ambiguity", sa.JSON(), nullable=False),
        sa.Column("verification_needed", sa.JSON(), nullable=False),
        sa.Column("matched_terms", sa.JSON(), nullable=False),
        sa.Column("unmatched_terms", sa.JSON(), nullable=False),
        sa.Column("raw_component_assessment", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["bulk_screening_items.id"],
            name=op.f("fk_bulk_screening_criterion_results_item_id_bulk_screening_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bulk_screening_criterion_results")),
    )
    op.create_index(
        op.f("ix_bulk_screening_criterion_results_item_id"), "bulk_screening_criterion_results", ["item_id"]
    )
    op.create_index(
        op.f("ix_bulk_screening_criterion_results_criterion_id"),
        "bulk_screening_criterion_results",
        ["criterion_id"],
    )

    op.create_table(
        "bulk_screening_evidence",
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["criterion_result_id"],
            ["bulk_screening_criterion_results.id"],
            name=op.f("fk_bulk_screening_evidence_criterion_result_id_bulk_screening_criterion_results"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bulk_screening_evidence")),
    )
    op.create_index(
        op.f("ix_bulk_screening_evidence_criterion_result_id"), "bulk_screening_evidence", ["criterion_result_id"]
    )

    op.create_table(
        "bulk_screening_work_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("status", item_status_enum, nullable=False),
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
            ["item_id"],
            ["bulk_screening_items.id"],
            name=op.f("fk_bulk_screening_work_items_item_id_bulk_screening_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bulk_screening_work_items")),
        sa.UniqueConstraint("item_id", name=op.f("uq_bulk_screening_work_items_item_id")),
    )
    op.create_index(op.f("ix_bulk_screening_work_items_status"), "bulk_screening_work_items", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_bulk_screening_work_items_status"), table_name="bulk_screening_work_items")
    op.drop_table("bulk_screening_work_items")
    op.drop_index(op.f("ix_bulk_screening_evidence_criterion_result_id"), table_name="bulk_screening_evidence")
    op.drop_table("bulk_screening_evidence")
    op.drop_index(
        op.f("ix_bulk_screening_criterion_results_criterion_id"), table_name="bulk_screening_criterion_results"
    )
    op.drop_index(op.f("ix_bulk_screening_criterion_results_item_id"), table_name="bulk_screening_criterion_results")
    op.drop_table("bulk_screening_criterion_results")
    op.drop_index(op.f("ix_bulk_screening_items_classification"), table_name="bulk_screening_items")
    op.drop_index(op.f("ix_bulk_screening_items_status"), table_name="bulk_screening_items")
    op.drop_index(op.f("ix_bulk_screening_items_duplicate_of_item_id"), table_name="bulk_screening_items")
    op.drop_index(op.f("ix_bulk_screening_items_content_sha256"), table_name="bulk_screening_items")
    op.drop_index(op.f("ix_bulk_screening_items_resume_document_id"), table_name="bulk_screening_items")
    op.drop_index(op.f("ix_bulk_screening_items_batch_id"), table_name="bulk_screening_items")
    op.drop_table("bulk_screening_items")
    op.drop_index(op.f("ix_bulk_screening_batches_status"), table_name="bulk_screening_batches")
    op.drop_index(op.f("ix_bulk_screening_batches_ad_hoc_jd_document_id"), table_name="bulk_screening_batches")
    op.drop_index(op.f("ix_bulk_screening_batches_rubric_version_id"), table_name="bulk_screening_batches")
    op.drop_index(op.f("ix_bulk_screening_batches_job_id"), table_name="bulk_screening_batches")
    op.drop_index(op.f("ix_bulk_screening_batches_source_type"), table_name="bulk_screening_batches")
    op.drop_index(op.f("ix_bulk_screening_batches_created_by_id"), table_name="bulk_screening_batches")
    op.drop_table("bulk_screening_batches")
    classification_enum.drop(op.get_bind(), checkfirst=True)
    item_status_enum.drop(op.get_bind(), checkfirst=True)
    batch_status_enum.drop(op.get_bind(), checkfirst=True)
    source_type_enum.drop(op.get_bind(), checkfirst=True)
