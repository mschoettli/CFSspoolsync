"""Add app settings table.

Revision ID: 20260417_0002
Revises: 20260417_0001
Create Date: 2026-04-17 00:02:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_0002"
down_revision: Union[str, None] = "20260417_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_settings_id"), "app_settings", ["id"], unique=False)
    op.create_index(op.f("ix_app_settings_key"), "app_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_app_settings_key"), table_name="app_settings")
    op.drop_index(op.f("ix_app_settings_id"), table_name="app_settings")
    op.drop_table("app_settings")
