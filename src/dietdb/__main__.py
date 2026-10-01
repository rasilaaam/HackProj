"""
DietDB - Main CLI and build orchestration
"""

import sys
import argparse
from pathlib import Path
import logging
from dietdb.db import DatabaseManager
from dietdb.ingest.ifct_simple import IfctLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def build_database(db_path: str = "data/diet.db", output_hash: bool = False) -> None:
    """Build database from clean checkout"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Initializing database at {db_path}")
    db_manager = DatabaseManager(db_path)

    # Initialize schema
    db_manager.init_db()
    logger.info("Schema initialized")

    # Load IFCT 2017 data
    ifct_loader = IfctLoader(db_path)
    ifct_loader.load()
    logger.info("IFCT 2017 data loaded")

    if output_hash:
        hash_val = db_manager.get_db_hash()
        logger.info(f"Database hash: {hash_val}")
        print(hash_val)


def main():
    parser = argparse.ArgumentParser(description="DietDB - Diet Planning Engine")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build database from scratch")
    build_parser.add_argument("--db", default="data/diet.db", help="Database path")
    build_parser.add_argument("--output-hash", action="store_true", help="Output database hash")

    args = parser.parse_args()

    if args.command == "build":
        build_database(args.db, args.output_hash)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
