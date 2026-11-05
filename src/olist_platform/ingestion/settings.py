"""Runtime settings read from environment variables (and ``.env`` when running locally)."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LANDING_DIR = Path("data/landing")


def load_dotenv_if_present() -> None:
    """Load ``.env`` without overriding variables already set (e.g. by docker compose)."""
    from dotenv import load_dotenv

    load_dotenv(override=False)


def landing_dir() -> Path:
    """Directory where the Kaggle CSVs are stored."""
    return Path(os.environ.get("OLIST_LANDING_DIR", DEFAULT_LANDING_DIR))


@dataclass(frozen=True)
class WarehouseSettings:
    """Connection settings for the PostgreSQL warehouse."""

    host: str
    port: int
    dbname: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "WarehouseSettings":
        """Build settings from ``WAREHOUSE_*`` environment variables."""
        missing = [
            name
            for name in ("WAREHOUSE_DB", "WAREHOUSE_USER", "WAREHOUSE_PASSWORD")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
        return cls(
            host=os.environ.get("WAREHOUSE_HOST", "localhost"),
            port=int(os.environ.get("WAREHOUSE_PORT", "5432")),
            dbname=os.environ["WAREHOUSE_DB"],
            user=os.environ["WAREHOUSE_USER"],
            password=os.environ["WAREHOUSE_PASSWORD"],
        )

    def conninfo(self) -> str:
        """libpq connection string, escaped (password included; never log it)."""
        from psycopg.conninfo import make_conninfo

        return make_conninfo(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
        )
