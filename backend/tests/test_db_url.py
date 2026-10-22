import pytest

from app.db import _normalise_url


@pytest.mark.parametrize(
    "given, expected",
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg2://u:p@host/db?sslmode=require"),
        ("postgresql+psycopg2://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),  # already explicit: untouched
        ("sqlite:///./restockiq.db", "sqlite:///./restockiq.db"),
    ],
)
def test_database_urls_name_the_psycopg2_driver(given, expected):
    assert _normalise_url(given) == expected


def test_a_normalised_postgres_url_builds_an_engine_without_connecting():
    from sqlalchemy import create_engine

    engine = create_engine(_normalise_url("postgresql://u:p@localhost:5432/db"))  # loads psycopg2, no connection yet
    assert engine.dialect.driver == "psycopg2"
