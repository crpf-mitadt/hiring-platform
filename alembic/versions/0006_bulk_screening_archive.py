"""bulk screening archive

Revision ID: 0006_bulk_screening_archive
Revises: 0005_bulk_screening
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_bulk_screening_archive"
down_revision: str | None = "0005_bulk_screening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bulk_screening_batches", sa.Column("target_designation", sa.String(length=160), nullable=True))
    op.add_column("bulk_screening_batches", sa.Column("failure_code", sa.String(length=120), nullable=True))
    op.add_column("bulk_screening_batches", sa.Column("failure_message", sa.Text(), nullable=True))
    op.add_column("bulk_screening_batches", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bulk_screening_batches", sa.Column("archived_by_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        op.f("fk_bulk_screening_batches_archived_by_id_users"),
        "bulk_screening_batches",
        "users",
        ["archived_by_id"],
        ["id"],
    )
    op.create_index(op.f("ix_bulk_screening_batches_archived_at"), "bulk_screening_batches", ["archived_at"])
    op.create_index(op.f("ix_bulk_screening_batches_archived_by_id"), "bulk_screening_batches", ["archived_by_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_bulk_screening_batches_archived_by_id"), table_name="bulk_screening_batches")
    op.drop_index(op.f("ix_bulk_screening_batches_archived_at"), table_name="bulk_screening_batches")
    op.drop_constraint(
        op.f("fk_bulk_screening_batches_archived_by_id_users"),
        "bulk_screening_batches",
        type_="foreignkey",
    )
    op.drop_column("bulk_screening_batches", "archived_by_id")
    op.drop_column("bulk_screening_batches", "archived_at")
    op.drop_column("bulk_screening_batches", "failure_message")
    op.drop_column("bulk_screening_batches", "failure_code")
    op.drop_column("bulk_screening_batches", "target_designation")
