"""search vocabulary with trigram index for typo correction

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-02 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every lower-cased word of an open job's title, and every skill, once. Refreshed when the
# jobs change (services/query_understanding.py), so corrections point at real vocabulary.
VIEW = """
CREATE MATERIALIZED VIEW search_terms AS
SELECT term, sum(n)::int AS jobs FROM (
    SELECT lower(w) AS term, 1 AS n
    FROM jobs, regexp_split_to_table(title, '[^A-Za-z0-9+#.]+') AS w
    WHERE status = 'open' AND length(w) >= 2
    UNION ALL
    SELECT lower(s) AS term, 1 AS n
    FROM jobs, unnest(skills) AS s
    WHERE status = 'open'
) t
GROUP BY term
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch")
    op.execute(VIEW)
    op.execute("CREATE UNIQUE INDEX uq_search_terms_term ON search_terms (term)")
    op.execute("CREATE INDEX ix_search_terms_trgm ON search_terms USING gin (term gin_trgm_ops)")
    # Trigram index on titles for substring/typo-tolerant title matches.
    op.execute("CREATE INDEX ix_jobs_title_trgm ON jobs USING gin (lower(title) gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_title_trgm")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS search_terms")
