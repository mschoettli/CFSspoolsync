"""Normalize tare defaults and seed starter dataset.

Revision ID: 20260417_0003
Revises: 20260417_0002
Create Date: 2026-04-17 00:03:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_0003"
down_revision: Union[str, None] = "20260417_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("tare_defaults")
    op.create_table(
        "tare_defaults",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("manufacturer", sa.String(), nullable=False),
        sa.Column("material", sa.String(), nullable=False),
        sa.Column("empty_spool_weight_g", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tare_defaults_id"), "tare_defaults", ["id"], unique=False)
    op.create_index(op.f("ix_tare_defaults_manufacturer"), "tare_defaults", ["manufacturer"], unique=False)
    op.create_index(op.f("ix_tare_defaults_material"), "tare_defaults", ["material"], unique=False)

    tare_defaults = sa.table(
        "tare_defaults",
        sa.column("manufacturer", sa.String()),
        sa.column("material", sa.String()),
        sa.column("empty_spool_weight_g", sa.Float()),
    )
    op.bulk_insert(
        tare_defaults,
        [
            {"manufacturer": "3D-Fuel", "material": "PLA", "empty_spool_weight_g": 155.0},
            {"manufacturer": "3D-Fuel", "material": "PETG", "empty_spool_weight_g": 155.0},
            {"manufacturer": "3D-Fuel", "material": "ABS", "empty_spool_weight_g": 155.0},
            {"manufacturer": "Filamentive", "material": "PLA", "empty_spool_weight_g": 180.0},
            {"manufacturer": "Filamentive", "material": "PETG", "empty_spool_weight_g": 180.0},
            {"manufacturer": "Filamentive", "material": "ABS", "empty_spool_weight_g": 180.0},
            {"manufacturer": "Bambu Lab", "material": "PLA", "empty_spool_weight_g": 210.0},
            {"manufacturer": "Bambu Lab", "material": "PETG", "empty_spool_weight_g": 210.0},
            {"manufacturer": "Bambu Lab", "material": "ABS", "empty_spool_weight_g": 210.0},
            {"manufacturer": "Prusament", "material": "PLA", "empty_spool_weight_g": 200.0},
            {"manufacturer": "Prusament", "material": "PETG", "empty_spool_weight_g": 200.0},
            {"manufacturer": "Prusament", "material": "ASA", "empty_spool_weight_g": 200.0},
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tare_defaults_material"), table_name="tare_defaults")
    op.drop_index(op.f("ix_tare_defaults_manufacturer"), table_name="tare_defaults")
    op.drop_index(op.f("ix_tare_defaults_id"), table_name="tare_defaults")
    op.drop_table("tare_defaults")

    op.create_table(
        "tare_defaults",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_key", sa.String(), nullable=False),
        sa.Column("brand_label", sa.String(), nullable=False),
        sa.Column("tare_weight_g", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tare_defaults_id"), "tare_defaults", ["id"], unique=False)
    op.create_index(op.f("ix_tare_defaults_brand_key"), "tare_defaults", ["brand_key"], unique=True)
