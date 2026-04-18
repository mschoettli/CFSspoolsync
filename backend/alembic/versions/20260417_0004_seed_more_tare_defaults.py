"""Add curated tare defaults and enforce manufacturer+material uniqueness.

Revision ID: 20260417_0004
Revises: 20260417_0003
Create Date: 2026-04-17 00:04:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_0004"
down_revision: Union[str, None] = "20260417_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_ROWS = [
    # Source set:
    # - https://www.onlyspoolz.com/portfolio/
    # - https://wiki.polymaker.com/polymaker-products/about-polymaker/polymaker-faq
    # - https://toddpearsall.com/2024/03/bambu-lab-spool-weights/
    {"manufacturer": "Bambu Lab", "material": "PLA", "empty_spool_weight_g": 251.0},
    {"manufacturer": "Bambu Lab", "material": "PETG", "empty_spool_weight_g": 251.0},
    {"manufacturer": "Bambu Lab", "material": "ABS", "empty_spool_weight_g": 251.0},
    {"manufacturer": "Prusament", "material": "PLA", "empty_spool_weight_g": 205.0},
    {"manufacturer": "Prusament", "material": "PETG", "empty_spool_weight_g": 205.0},
    {"manufacturer": "Prusament", "material": "ASA", "empty_spool_weight_g": 205.0},
    {"manufacturer": "Polymaker", "material": "PLA", "empty_spool_weight_g": 140.0},
    {"manufacturer": "Polymaker", "material": "PETG", "empty_spool_weight_g": 140.0},
    {"manufacturer": "eSUN", "material": "PLA", "empty_spool_weight_g": 242.0},
    {"manufacturer": "eSUN", "material": "PETG", "empty_spool_weight_g": 242.0},
    {"manufacturer": "SUNLU", "material": "PLA", "empty_spool_weight_g": 124.0},
    {"manufacturer": "SUNLU", "material": "PETG", "empty_spool_weight_g": 124.0},
    {"manufacturer": "Overture", "material": "PLA", "empty_spool_weight_g": 171.0},
    {"manufacturer": "Overture", "material": "PETG", "empty_spool_weight_g": 171.0},
    {"manufacturer": "Elegoo", "material": "PLA", "empty_spool_weight_g": 160.0},
    {"manufacturer": "Elegoo", "material": "PETG", "empty_spool_weight_g": 160.0},
]


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(
        sa.text(
            """
            DELETE FROM tare_defaults
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM tare_defaults
                GROUP BY manufacturer, material
            )
            """
        )
    )

    op.create_index(
        "ux_tare_defaults_manufacturer_material",
        "tare_defaults",
        ["manufacturer", "material"],
        unique=True,
    )

    for row in SEED_ROWS:
        existing = bind.execute(
            sa.text(
                """
                SELECT id
                FROM tare_defaults
                WHERE manufacturer = :manufacturer AND material = :material
                """
            ),
            row,
        ).fetchone()
        if existing:
            bind.execute(
                sa.text(
                    """
                    UPDATE tare_defaults
                    SET empty_spool_weight_g = :empty_spool_weight_g,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE manufacturer = :manufacturer AND material = :material
                    """
                ),
                row,
            )
        else:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO tare_defaults (manufacturer, material, empty_spool_weight_g)
                    VALUES (:manufacturer, :material, :empty_spool_weight_g)
                    """
                ),
                row,
            )


def downgrade() -> None:
    op.drop_index("ux_tare_defaults_manufacturer_material", table_name="tare_defaults")
