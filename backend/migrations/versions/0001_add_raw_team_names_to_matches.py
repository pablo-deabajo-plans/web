from __future__ import annotations

from typing import Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS raw_home_team TEXT")
    op.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS raw_away_team TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE matches DROP COLUMN IF EXISTS raw_home_team")
    op.execute("ALTER TABLE matches DROP COLUMN IF EXISTS raw_away_team")
