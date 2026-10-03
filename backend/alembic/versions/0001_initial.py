"""Initial schema – all tables (idempotent: CREATE ... IF NOT EXISTS).

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-03
"""
from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

STATEMENTS = [
    """
CREATE TABLE IF NOT EXISTS organization (
    id UUID NOT NULL,
    slug VARCHAR(64) NOT NULL,
    name VARCHAR(200) NOT NULL,
    status VARCHAR(16) NOT NULL,
    contact_email VARCHAR(320),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_org_status CHECK (status IN ('active','suspended')),
    UNIQUE (slug)
)
    """,
    """
CREATE TABLE IF NOT EXISTS platform_admin (
    id UUID NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (email)
)
    """,
    """
CREATE TABLE IF NOT EXISTS app_user (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    email VARCHAR(320) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_app_user_org_email UNIQUE (organization_id, email),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_app_user_organization_id ON app_user (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID NOT NULL,
    platform_admin_id UUID,
    platform_admin_email VARCHAR(320),
    organization_id UUID,
    action VARCHAR(120) NOT NULL,
    method VARCHAR(10),
    path TEXT,
    detail JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(platform_admin_id) REFERENCES platform_admin (id) ON DELETE SET NULL,
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE SET NULL
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_audit_log_organization_id ON audit_log (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS device_token (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    label VARCHAR(100) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    time_offset_seconds INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_device_token_label UNIQUE (organization_id, label),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_device_token_organization_id ON device_token (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS event (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    name VARCHAR(200) NOT NULL,
    year INTEGER NOT NULL,
    event_date DATE,
    registration_deadline TIMESTAMP WITH TIME ZONE,
    default_start_time TIMESTAMP WITH TIME ZONE,
    tshirt_options TEXT NOT NULL,
    tshirt_included BOOLEAN NOT NULL,
    youth_cutoff_date DATE,
    venue_postal_code VARCHAR(10),
    bib_start_number INTEGER NOT NULL,
    certificate_offset_lines INTEGER NOT NULL,
    certificate_background BYTEA,
    certificate_background_mime VARCHAR(64),
    bib_background BYTEA,
    bib_background_mime VARCHAR(64),
    photo_base_url TEXT,
    photo_hmac_seed VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_event_organization_id ON event (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS org_setting (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    key VARCHAR(64) NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_org_setting_key UNIQUE (organization_id, key),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_org_setting_organization_id ON org_setting (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS participant (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    birth_date DATE NOT NULL,
    gender VARCHAR(1) NOT NULL,
    match_key VARCHAR(300) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_participant_org_match UNIQUE (organization_id, match_key),
    CONSTRAINT ck_participant_gender CHECK (gender IN ('f','m','x')),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_participant_organization_id ON participant (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS platform_session (
    id UUID NOT NULL,
    platform_admin_id UUID NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    acting_organization_id UUID,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(platform_admin_id) REFERENCES platform_admin (id) ON DELETE CASCADE,
    UNIQUE (token_hash),
    FOREIGN KEY(acting_organization_id) REFERENCES organization (id) ON DELETE SET NULL
)
    """,
    """
CREATE TABLE IF NOT EXISTS site_asset (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    key VARCHAR(64) NOT NULL,
    data BYTEA NOT NULL,
    mime VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_site_asset_key UNIQUE (organization_id, key),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_site_asset_organization_id ON site_asset (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS sponsor (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    tier INTEGER NOT NULL,
    name VARCHAR(200),
    url TEXT,
    image BYTEA NOT NULL,
    mime VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_sponsor_tier CHECK (tier BETWEEN 1 AND 5),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_sponsor_organization_id ON sponsor (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS auth_token (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES app_user (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_auth_token_organization_id ON auth_token (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS competition (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    event_id UUID NOT NULL,
    title_de VARCHAR(200) NOT NULL,
    title_en VARCHAR(200) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE,
    price_adult_cents INTEGER NOT NULL,
    price_youth_cents INTEGER,
    age_class_scheme VARCHAR(8) NOT NULL,
    gender_scoring BOOLEAN NOT NULL,
    relay_scoring BOOLEAN NOT NULL,
    bib_range_start INTEGER,
    bib_range_end INTEGER,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_comp_scheme CHECK (age_class_scheme IN ('five','one','none')),
    CONSTRAINT ck_comp_bib_range CHECK ((bib_range_start IS NULL AND bib_range_end IS NULL) OR (bib_range_start IS NOT NULL AND bib_range_end IS NOT NULL AND bib_range_start <= bib_range_end)),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES event (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_competition_event_id ON competition (event_id)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_competition_organization_id ON competition (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS timing_record (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    event_id UUID NOT NULL,
    bib_number INTEGER NOT NULL,
    absolute_time TIMESTAMP WITH TIME ZONE NOT NULL,
    source_token_id UUID,
    source_label VARCHAR(100),
    dedup_key VARCHAR(120) NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_timing_event_dedup UNIQUE (event_id, dedup_key),
    CONSTRAINT ck_timing_status CHECK (status IN ('valid','ignored','duplicate','manual')),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES event (id) ON DELETE CASCADE,
    FOREIGN KEY(source_token_id) REFERENCES device_token (id) ON DELETE SET NULL
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_timing_record_event_id ON timing_record (event_id)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_timing_record_bib_number ON timing_record (bib_number)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_timing_record_organization_id ON timing_record (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS user_role (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role VARCHAR(32) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_user_role UNIQUE (user_id, role),
    CONSTRAINT ck_user_role_role CHECK (role IN ('admin','race_office','timing','sponsor_management','sepa','viewer')),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES app_user (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_user_role_organization_id ON user_role (organization_id)
    """,
    """
CREATE TABLE IF NOT EXISTS registration (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    event_id UUID NOT NULL,
    competition_id UUID NOT NULL,
    participant_id UUID NOT NULL,
    status VARCHAR(16) NOT NULL,
    email VARCHAR(320) NOT NULL,
    language VARCHAR(2) NOT NULL,
    team_name VARCHAR(120),
    tshirt_size VARCHAR(40),
    postal_code VARCHAR(10),
    heard_about VARCHAR(40),
    consent_data BOOLEAN NOT NULL,
    consent_publish BOOLEAN NOT NULL,
    manage_token_hash VARCHAR(64) NOT NULL,
    finish_seconds NUMERIC(10, 2),
    relay_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_registration_event_participant UNIQUE (event_id, participant_id),
    CONSTRAINT ck_reg_status CHECK (status IN ('pending','confirmed','cancelled')),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES event (id) ON DELETE CASCADE,
    FOREIGN KEY(competition_id) REFERENCES competition (id) ON DELETE RESTRICT,
    FOREIGN KEY(participant_id) REFERENCES participant (id) ON DELETE RESTRICT,
    UNIQUE (manage_token_hash)
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_registration_organization_id ON registration (organization_id)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_registration_event_id ON registration (event_id)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_registration_relay_id ON registration (relay_id)
    """,
    """
CREATE TABLE IF NOT EXISTS bib_assignment (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    event_id UUID NOT NULL,
    registration_id UUID NOT NULL,
    bib_number INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_bib_event_number UNIQUE (event_id, bib_number),
    CONSTRAINT uq_bib_registration UNIQUE (registration_id),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES event (id) ON DELETE CASCADE,
    FOREIGN KEY(registration_id) REFERENCES registration (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_bib_assignment_organization_id ON bib_assignment (organization_id)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_bib_assignment_event_id ON bib_assignment (event_id)
    """,
    """
CREATE TABLE IF NOT EXISTS payment (
    id UUID NOT NULL,
    organization_id UUID NOT NULL,
    registration_id UUID NOT NULL,
    method VARCHAR(16) NOT NULL,
    amount_cents INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL,
    iban_encrypted TEXT,
    iban_masked VARCHAR(40),
    account_holder VARCHAR(200),
    mandate_reference VARCHAR(35),
    sepa_exported_at TIMESTAMP WITH TIME ZONE,
    provider_checkout_id VARCHAR(120),
    provider_checkout_reference VARCHAR(120),
    provider_transaction_code VARCHAR(120),
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_payment_registration UNIQUE (registration_id),
    CONSTRAINT uq_payment_org_mandate UNIQUE (organization_id, mandate_reference),
    CONSTRAINT ck_payment_method CHECK (method IN ('sepa_debit','on_site','sumup')),
    CONSTRAINT ck_payment_status CHECK (status IN ('pending','paid','cancelled')),
    FOREIGN KEY(organization_id) REFERENCES organization (id) ON DELETE CASCADE,
    FOREIGN KEY(registration_id) REFERENCES registration (id) ON DELETE CASCADE
)
    """,
    """
CREATE INDEX IF NOT EXISTS ix_payment_organization_id ON payment (organization_id)
    """,
]

TABLES = ['payment', 'bib_assignment', 'registration', 'user_role', 'timing_record', 'competition', 'auth_token', 'sponsor', 'site_asset', 'platform_session', 'participant', 'org_setting', 'event', 'device_token', 'audit_log', 'app_user', 'platform_admin', 'organization']


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
