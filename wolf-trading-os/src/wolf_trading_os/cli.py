"""Command-line interface.

Commands:
    import-option-alpha FILE [FILE ...]   Import Option Alpha CSV exports
    run-dashboard                         Launch the Streamlit dashboard
    database-upgrade                      Run Alembic migrations to head
    database-reset-dev --yes              Drop + recreate schema (development ONLY)

There is deliberately no command related to orders, signals, or execution.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alembic.config import Config

from wolf_trading_os.config import get_settings
from wolf_trading_os.logging import configure_logging, get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wolf-trading-os",
        description="Wolf Trading OS Phase 1 — analytics only, no order capability.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser(
        "import-option-alpha", help="Import one or more Option Alpha CSV exports"
    )
    p_import.add_argument("files", nargs="+", type=Path, help="CSV file paths")
    p_import.add_argument(
        "--date-order",
        choices=["MDY", "DMY"],
        default="MDY",
        help="Slash-date convention of the export (default MDY, the "
        "confirmed Option Alpha format); contradictory in-file evidence "
        "rejects the file",
    )

    sub.add_parser("run-dashboard", help="Launch the Streamlit dashboard")

    sub.add_parser("database-upgrade", help="Run Alembic migrations to head")

    p_reset = sub.add_parser(
        "database-reset-dev",
        help="Drop and recreate the schema (blocked outside development "
        "and outside local dev-named databases)",
    )
    p_reset.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destruction of all data in the development database",
    )
    p_reset.add_argument(
        "--force-unsafe-reset",
        action="store_true",
        help="Override the local-host/dev-name safety checks (still requires "
        "--confirm-database naming the exact target database)",
    )
    p_reset.add_argument(
        "--confirm-database",
        metavar="NAME",
        default=None,
        help="Second confirmation for --force-unsafe-reset: must equal the "
        "target database name exactly",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    handlers = {
        "import-option-alpha": _cmd_import_option_alpha,
        "run-dashboard": _cmd_run_dashboard,
        "database-upgrade": _cmd_database_upgrade,
        "database-reset-dev": _cmd_database_reset_dev,
    }
    result: int = handlers[args.command](args)
    return result


def _cmd_import_option_alpha(args: argparse.Namespace) -> int:
    from wolf_trading_os.ingestion.option_alpha import OptionAlphaImporter

    missing = [f for f in args.files if not f.is_file()]
    if missing:
        print(f"error: file(s) not found: {', '.join(map(str, missing))}", file=sys.stderr)
        return 2

    summary = OptionAlphaImporter(date_order=args.date_order).import_files(args.files)
    print(json.dumps(summary.as_report(), indent=2, default=str))
    return 0 if all(f.ok for f in summary.files) else 1


def _cmd_run_dashboard(_: argparse.Namespace) -> int:
    app_path = Path(__file__).parent / "dashboard" / "app.py"
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(app_path)],
    )


def _cmd_database_upgrade(_: argparse.Namespace) -> int:
    from alembic import command

    command.upgrade(_alembic_config(), "head")
    logger.info("database_upgrade_complete")
    return 0


# Reset safety (audit finding M5): environment gating alone is not enough —
# a dev-configured machine pointing at a shared database must still refuse.
_RESET_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "db"}
_RESET_DEV_NAME = re.compile(r"(dev|test|local|scratch|sandbox)", re.IGNORECASE)


def _reset_refusal_reason(database_url: str, args: argparse.Namespace) -> str | None:
    """Why a reset must be refused, or None if it may proceed.

    Passwords are never included in any message: URLs are rendered via
    SQLAlchemy's default masking.
    """
    import os

    from sqlalchemy.engine import make_url

    if os.environ.get("WTOS_ENVIRONMENT") != "development":
        return (
            "WTOS_ENVIRONMENT must be EXPLICITLY set to 'development' "
            f"(currently: {os.environ.get('WTOS_ENVIRONMENT') or 'unset'})"
        )
    settings = get_settings()
    if not settings.is_development:
        return f"settings environment is {settings.environment.value}, not development"

    try:
        url = make_url(database_url)
    except Exception:
        return "database URL is missing or malformed"
    if url.host is None or url.database is None:
        return "database URL is missing a host or database name"

    host_ok = url.host in _RESET_ALLOWED_HOSTS
    name_ok = bool(_RESET_DEV_NAME.search(url.database))
    if host_ok and name_ok:
        return None

    # Override path: explicit destructive flag + exact-name confirmation.
    if args.force_unsafe_reset:
        if args.confirm_database != url.database:
            return (
                f"--force-unsafe-reset requires --confirm-database {url.database!r} "
                f"(target: host={url.host} database={url.database})"
            )
        print(
            f"WARNING: forced reset of host={url.host} database={url.database}",
            file=sys.stderr,
        )
        return None

    problems = []
    if not host_ok:
        problems.append(f"host {url.host!r} is not a local development host")
    if not name_ok:
        problems.append(
            f"database name {url.database!r} does not look like a development/test database"
        )
    return "; ".join(problems) + " (use --force-unsafe-reset with --confirm-database)"


def _cmd_database_reset_dev(args: argparse.Namespace) -> int:
    """Drop and recreate all tables. Fails closed outside development
    environments AND outside local dev-named databases (M5)."""
    settings = get_settings()
    reason = _reset_refusal_reason(settings.database_url, args)
    if reason is not None:
        print(f"REFUSED: {reason}", file=sys.stderr)
        return 3
    if not args.yes:
        print("Refusing to reset without --yes (this destroys all data).", file=sys.stderr)
        return 2

    from alembic import command
    from sqlalchemy.engine import make_url

    from wolf_trading_os.database import get_engine
    from wolf_trading_os.database.orm import Base

    url = make_url(settings.database_url)
    print(f"Resetting host={url.host} database={url.database}", file=sys.stderr)
    engine = get_engine()
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    command.upgrade(_alembic_config(), "head")
    logger.warning(
        "database_reset_dev_complete",
        environment=settings.environment.value,
        host=url.host,
        database=url.database,
    )
    return 0


def _alembic_config() -> Config:
    from alembic.config import Config

    ini = _PROJECT_ROOT / "alembic.ini"
    if not ini.is_file():
        # Installed (non-editable) layout: fall back to CWD.
        ini = Path.cwd() / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("script_location", str(ini.parent / "migrations"))
    return config


if __name__ == "__main__":
    raise SystemExit(main())
