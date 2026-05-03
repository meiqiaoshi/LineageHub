"""Command-line interface for LineageHub."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from lineagehub.graph import (
    get_direct_downstream,
    get_direct_upstream,
    get_downstream,
    get_upstream,
    impact_analysis,
)
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

    depth_opt = {
        "choices": ["direct", "all"],
        "default": "all",
        "help": "direct: immediate neighbors only; all: full transitive closure (default)",
    }

    p_up = sub.add_parser("upstream", help="List upstream datasets for a dataset")
    p_up.add_argument("dataset", help="Dataset name")
    p_up.add_argument("--depth", **depth_opt)

    p_down = sub.add_parser("downstream", help="List downstream datasets for a dataset")
    p_down.add_argument("dataset", help="Dataset name")
    p_down.add_argument("--depth", **depth_opt)

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
                rows = (
                    get_direct_upstream(store, args.dataset)
                    if args.depth == "direct"
                    else get_upstream(store, args.dataset)
                )
                label = "Direct upstream" if args.depth == "direct" else "Upstream"
                print(f"{label} dependencies for {args.dataset}:\n")
                _print_bullets(rows)
                return 0
            case "downstream":
                rows = (
                    get_direct_downstream(store, args.dataset)
                    if args.depth == "direct"
                    else get_downstream(store, args.dataset)
                )
                label = "Direct downstream" if args.depth == "direct" else "Downstream"
                print(f"{label} datasets from {args.dataset}:\n")
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
