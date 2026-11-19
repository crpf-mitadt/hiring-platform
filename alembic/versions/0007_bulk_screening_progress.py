"""bulk screening progress

Revision ID: 0007_bulk_screening_progress
Revises: 0006_bulk_screening_archive
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_bulk_screening_progress"
down_revision: str | None = "0006_bulk_screening_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bulk_screening_batches",
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("bulk_screening_items", sa.Column("processing_stage", sa.String(length=50), nullable=True))
    op.add_column(
        "bulk_screening_items",
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("bulk_screening_items", sa.Column("stage_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bulk_screening_work_items", sa.Column("processing_stage", sa.String(length=50), nullable=True))
    op.add_column(
        "bulk_screening_work_items",
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "bulk_screening_work_items",
        sa.Column("stage_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bulk_screening_work_items", "stage_updated_at")
    op.drop_column("bulk_screening_work_items", "progress_percent")
    op.drop_column("bulk_screening_work_items", "processing_stage")
    op.drop_column("bulk_screening_items", "stage_updated_at")
    op.drop_column("bulk_screening_items", "progress_percent")
    op.drop_column("bulk_screening_items", "processing_stage")
    op.drop_column("bulk_screening_batches", "progress_percent")
