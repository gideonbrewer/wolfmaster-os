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
        help="Drop and recreate the schema (blocked outside development)",
    )
    p_reset.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destruction of all data in the development database",
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


def _cmd_database_reset_dev(args: argparse.Namespace) -> int:
    """Drop and recreate all tables. Fails closed outside development."""
    settings = get_settings()
    if not settings.is_development:
        print(
            "REFUSED: database-reset-dev is only available when "
            f"WTOS_ENVIRONMENT=development (current: {settings.environment.value}).",
            file=sys.stderr,
        )
        return 3
    if not args.yes:
        print("Refusing to reset without --yes (this destroys all data).", file=sys.stderr)
        return 2

    from alembic import command

    from wolf_trading_os.database import get_engine
    from wolf_trading_os.database.orm import Base

    engine = get_engine()
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    command.upgrade(_alembic_config(), "head")
    logger.warning("database_reset_dev_complete", environment=settings.environment.value)
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
