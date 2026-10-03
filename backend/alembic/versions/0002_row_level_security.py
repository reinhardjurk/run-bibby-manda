"""Row-level security policies on every tenant table (defense in depth).

The application publishes the current tenant via `set_config('app.organization_id', ...)`.
Policies only take effect for roles without BYPASSRLS that do not own the tables – production
connects with such a restricted role (see docs/ARCHITECTURE.md). Idempotent.

Revision ID: 0002_row_level_security
Revises: 0001_initial
Create Date: 2026-10-03
"""
from __future__ import annotations

from alembic import op

revision = "0002_row_level_security"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "app_user", "user_role", "auth_token", "event", "competition", "participant", "registration",
    "bib_assignment", "payment", "device_token", "timing_record", "sponsor", "site_asset",
    "org_setting",
]


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            "USING (organization_id::text = current_setting('app.organization_id', true)) "
            "WITH CHECK (organization_id::text = current_setting('app.organization_id', true))"
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
