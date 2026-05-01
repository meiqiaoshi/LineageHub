"""Command-line interface for LineageHub."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from lineagehub.graph import get_downstream, get_upstream, impact_analysis
from lineagehub.loader import load_lineage_json
from lineagehub.store import MetadataStore


def default_db_path() -> str:
    return os.environ.get("LINEAGEHUB_DB", "lineagehub.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lineagehub", description="Local dataset lineage metadata.")
    parser.add_argument(
        "--db",
        default=default_db_path(),
        metavar="PATH",
        help="SQLite database path (default: ./lineagehub.db or LINEAGEHUB_DB)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_load = sub.add_parser("load", help="Load lineage metadata from a JSON file")
    p_load.add_argument("path", type=Path, help="Path to lineage JSON")

    p_up = sub.add_parser("upstream", help="List transitive upstream datasets")
    p_up.add_argument("dataset", help="Dataset name")

    p_down = sub.add_parser("downstream", help="List transitive downstream datasets")
    p_down.add_argument("dataset", help="Dataset name")

    p_impact = sub.add_parser("impact", help="List datasets affected if this asset fails")
    p_impact.add_argument("dataset", help="Dataset name")

    args = parser.parse_args(argv)
    db_path = Path(args.db)
    store = MetadataStore(db_path)

    try:
        match args.command:
            case "load":
                load_lineage_json(store, args.path)
                print(f"Loaded lineage metadata from {args.path} into {db_path.resolve()}")
                return 0
            case "upstream":
                rows = get_upstream(store, args.dataset)
                print(f"Upstream dependencies for {args.dataset}:\n")
                _print_bullets(rows)
                return 0
            case "downstream":
                rows = get_downstream(store, args.dataset)
                print(f"Downstream datasets from {args.dataset}:\n")
                _print_bullets(rows)
                return 0
            case "impact":
                rows = impact_analysis(store, args.dataset)
                print(f"Downstream assets affected by {args.dataset}:\n")
                _print_bullets(rows)
                return 0
            case _:
                raise RuntimeError(f"unhandled command: {args.command!r}")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1


def _print_bullets(names: list[str]) -> None:
    if not names:
        print("(none)")
        return
    for name in names:
        print(f"- {name}")


if __name__ == "__main__":
    raise SystemExit(main())
