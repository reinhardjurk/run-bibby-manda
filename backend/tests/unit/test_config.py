from app.config import normalize_database_url


def test_console_style_urls_are_mapped_to_asyncpg():
    src = "postgres://11111111-2222-3333-4444-555555555555:secret@abc.pg.sdb.fr-par.scw.cloud:5432/bibby?sslmode=require"
    assert normalize_database_url(src) == (
        "postgresql+asyncpg://11111111-2222-3333-4444-555555555555:secret@abc.pg.sdb.fr-par.scw.cloud:5432/bibby?ssl=require"
    )
    assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_pasted_whitespace_and_odd_sslmode_values_are_cleaned():
    assert normalize_database_url("  postgres://u:p@h:5432/db?sslmode=require \n") == (
        "postgresql+asyncpg://u:p@h:5432/db?ssl=require"
    )
    assert normalize_database_url(
        "postgres://u:p@h/db?sslmode=Verify-Full&application_name=bibby"
    ) == ("postgresql+asyncpg://u:p@h/db?ssl=verify-full&application_name=bibby")
    assert normalize_database_url("postgres://u:p@h/db?") == "postgresql+asyncpg://u:p@h/db"


def test_asyncpg_urls_are_left_alone():
    url = "postgresql+asyncpg://u:p@localhost:5432/bibby"
    assert normalize_database_url(url) == url
    assert normalize_database_url(url + "?ssl=require") == url + "?ssl=require"
