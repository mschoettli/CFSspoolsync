"""Initial schema for CFSspoolsync v3.

Revision ID: 20260417_0001
Revises:
Create Date: 2026-04-17 00:01:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "print_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("filament_used_start_raw", sa.Float(), nullable=True),
        sa.Column("filament_used_last_raw", sa.Float(), nullable=True),
        sa.Column("live_consumed_mm", sa.Float(), nullable=False),
        sa.Column("live_consumed_g", sa.Float(), nullable=False),
        sa.Column("live_consumed_quality", sa.String(), nullable=True),
        sa.Column("consumption_source", sa.String(), nullable=True),
        sa.Column("slot_a_spool_id", sa.Integer(), nullable=True),
        sa.Column("slot_b_spool_id", sa.Integer(), nullable=True),
        sa.Column("slot_c_spool_id", sa.Integer(), nullable=True),
        sa.Column("slot_d_spool_id", sa.Integer(), nullable=True),
        sa.Column("slot_a_before", sa.Float(), nullable=True),
        sa.Column("slot_a_after", sa.Float(), nullable=True),
        sa.Column("slot_b_before", sa.Float(), nullable=True),
        sa.Column("slot_b_after", sa.Float(), nullable=True),
        sa.Column("slot_c_before", sa.Float(), nullable=True),
        sa.Column("slot_c_after", sa.Float(), nullable=True),
        sa.Column("slot_d_before", sa.Float(), nullable=True),
        sa.Column("slot_d_after", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_print_jobs_id"), "print_jobs", ["id"], unique=False)

    op.create_table(
        "spools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("material", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("initial_weight", sa.Float(), nullable=False),
        sa.Column("remaining_weight", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("cfs_slot", sa.Integer(), nullable=True),
        sa.Column("diameter", sa.Float(), nullable=False),
        sa.Column("density", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_spools_id"), "spools", ["id"], unique=False)

    op.create_table(
        "tare_defaults",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_key", sa.String(), nullable=False),
        sa.Column("brand_label", sa.String(), nullable=False),
        sa.Column("tare_weight_g", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tare_defaults_brand_key"), "tare_defaults", ["brand_key"], unique=True)
    op.create_index(op.f("ix_tare_defaults_id"), "tare_defaults", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tare_defaults_id"), table_name="tare_defaults")
    op.drop_index(op.f("ix_tare_defaults_brand_key"), table_name="tare_defaults")
    op.drop_table("tare_defaults")

    op.drop_index(op.f("ix_spools_id"), table_name="spools")
    op.drop_table("spools")

    op.drop_index(op.f("ix_print_jobs_id"), table_name="print_jobs")
    op.drop_table("print_jobs")
