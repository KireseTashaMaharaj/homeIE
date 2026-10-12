from app.config import Settings


def _settings_with_database_env(monkeypatch, *, database_url: str | None = None) -> Settings:
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URI", raising=False)
    if database_url is not None:
        monkeypatch.setenv("DATABASE_URL", database_url)
    return Settings(_env_file=None)


def test_settings_accept_database_url(monkeypatch):
    database_url = "postgresql://db.example.test/homeie"

    settings = _settings_with_database_env(monkeypatch, database_url=database_url)

    assert settings.database_uri == database_url


def test_settings_keep_database_uri_compatibility(monkeypatch):
    database_uri = "sqlite:///database.db"
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URI", database_uri)

    settings = Settings(_env_file=None)

    assert settings.database_uri == database_uri
