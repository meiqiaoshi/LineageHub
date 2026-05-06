"""Command-line interface for LineageHub."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from lineagehub.graph import (
    analyze_run_impact,
    collect_graph_edges,
    get_direct_downstream,
    get_direct_upstream,
    get_downstream,
    get_upstream,
    impact_analysis,
    lineage_downstream_results,
    lineage_impact_results,
    lineage_upstream_results,
)
from lineagehub.analysis import summarize_failed_runs
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.output import (
    downstream_payload,
    dumps_json,
    format_edges_dot,
    format_edges_mermaid,
    format_edges_text,
    impact_payload,
    run_impact_payload,
    upstream_payload,
)
from lineagehub.store import MetadataStore, RunRecord


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

    p_load_runs = sub.add_parser("load-runs", help="Load pipeline run records from a JSON file")
    p_load_runs.add_argument("path", type=Path, help="Path to runs JSON")

    p_runs = sub.add_parser("runs", help="Operational queries over pipeline runs")
    runs_sub = p_runs.add_subparsers(dest="runs_command", required=True)

    p_runs_list = runs_sub.add_parser("list", help="List recent runs")
    p_runs_list.add_argument("--status", help="Filter by run status (e.g. failed)")
    p_runs_list.add_argument("--job", help="Filter by job name")
    p_runs_list.add_argument(
        "--since",
        help="Only include runs with started_at >= SINCE (ISO-8601 string)",
    )
    p_runs_list.add_argument("--limit", type=int, help="Max number of runs to return")
    p_runs_list.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_runs_latest = runs_sub.add_parser("latest", help="Show the most recent run for a job")
    p_runs_latest.add_argument("--job", required=True, help="Job name")
    p_runs_latest.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    depth_opt = {
        "choices": ["direct", "all"],
        "default": "all",
        "help": "direct: immediate neighbors only; all: full transitive closure (default)",
    }

    p_up = sub.add_parser("upstream", help="List upstream datasets for a dataset")
    p_up.add_argument("dataset", help="Dataset name")
    p_up.add_argument("--depth", **depth_opt)
    p_up.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_down = sub.add_parser("downstream", help="List downstream datasets for a dataset")
    p_down.add_argument("dataset", help="Dataset name")
    p_down.add_argument("--depth", **depth_opt)
    p_down.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_impact = sub.add_parser("impact", help="List datasets affected if this asset fails")
    p_impact.add_argument("dataset", help="Dataset name")
    p_impact.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_graph = sub.add_parser("graph", help="Export lineage edges for a dataset")
    p_graph.add_argument("dataset", help="Dataset name")
    p_graph.add_argument(
        "--direction",
        choices=["upstream", "downstream", "both"],
        default="downstream",
        help="Which edges to include (default: downstream)",
    )
    p_graph.add_argument("--depth", **depth_opt)
    p_graph.add_argument(
        "--format",
        choices=["text", "mermaid", "dot"],
        default="text",
        help="Output format (default: text)",
    )

    p_impact_run = sub.add_parser(
        "impact-run",
        help="Downstream impact starting from a recorded pipeline run's outputs",
    )
    p_impact_run.add_argument("run_id", help="External run id (e.g. run_001)")
    p_impact_run.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_incidents = sub.add_parser("incidents", help="Operational incident summaries")
    incidents_sub = p_incidents.add_subparsers(dest="incidents_command", required=True)

    p_inc_summarize = incidents_sub.add_parser(
        "summarize",
        help="Summarize matching runs and their downstream blast radius",
    )
    p_inc_summarize.add_argument(
        "--status",
        default="failed",
        help="Run status filter (default: failed)",
    )
    p_inc_summarize.add_argument(
        "--since",
        help="Only include runs with started_at >= SINCE (ISO-8601 string)",
    )
    p_inc_summarize.add_argument("--limit", type=int, help="Max number of runs to include")
    p_inc_summarize.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_inc_rank = incidents_sub.add_parser(
        "rank",
        help="Rank incidents by blast radius score",
    )
    p_inc_rank.add_argument(
        "--status",
        default="failed",
        help="Run status filter (default: failed)",
    )
    p_inc_rank.add_argument(
        "--since",
        help="Only include runs with started_at >= SINCE (ISO-8601 string)",
    )
    p_inc_rank.add_argument("--limit", type=int, help="Max number of incidents to return")
    p_inc_rank.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    args = parser.parse_args(argv)
    db_path = Path(args.db)
    store = MetadataStore(db_path)

    try:
        match args.command:
            case "load":
                load_lineage_json(store, args.path)
                print(f"Loaded lineage metadata from {args.path} into {db_path.resolve()}")
                return 0
            case "load-runs":
                load_runs_json(store, args.path)
                print(f"Loaded runs from {args.path} into {db_path.resolve()}")
                return 0
            case "runs":
                match args.runs_command:
                    case "list":
                        rows = store.list_runs(
                            status=args.status,
                            job_name=args.job,
                            since=args.since,
                            limit=args.limit,
                        )
                        if args.json:
                            payload = {
                                "query_type": "runs_list",
                                "filters": {
                                    "status": args.status,
                                    "job": args.job,
                                    "since": args.since,
                                    "limit": args.limit,
                                },
                                "runs": [_run_record_payload(r) for r in rows],
                            }
                            sys.stdout.write(dumps_json(payload))
                            return 0

                        print("Recent runs:\n")
                        if not rows:
                            print("(none)")
                            return 0
                        for r in rows:
                            rid = _run_display_id(r)
                            print(f"- {rid}")
                            print(f"  Job: {r.job_name}")
                            print(f"  Status: {r.status}")
                            if r.started_at is not None:
                                print(f"  Started: {r.started_at}")
                            if r.ended_at is not None:
                                print(f"  Ended: {r.ended_at}")
                        return 0
                    case "latest":
                        latest = store.get_latest_run(args.job)
                        if args.json:
                            payload = {
                                "query_type": "latest_run",
                                "job_name": args.job,
                                "run": _run_record_payload(latest) if latest is not None else None,
                            }
                            sys.stdout.write(dumps_json(payload))
                            return 0

                        print(f"Latest run for {args.job}:\n")
                        if latest is None:
                            print("(no runs)")
                            return 0
                        print(f"Run: {_run_display_id(latest)}")
                        print(f"Status: {latest.status}")
                        if latest.started_at is not None:
                            print(f"Started: {latest.started_at}")
                        if latest.ended_at is not None:
                            print(f"Ended: {latest.ended_at}")
                        return 0
                    case _:
                        raise RuntimeError(f"unhandled runs command: {args.runs_command!r}")
            case "incidents":
                match args.incidents_command:
                    case "summarize":
                        result = summarize_failed_runs(
                            store,
                            status=args.status,
                            since=args.since,
                            limit=args.limit,
                        )
                        if args.json:
                            sys.stdout.write(dumps_json(result))
                            return 0

                        status_label = args.status or "matching"
                        print(f"Incident summary for {status_label} runs:\n")
                        if result["incident_count"] == 0:
                            print("(none)")
                            return 0
                        for i, inc in enumerate(result["incidents"], start=1):
                            print(f"{i}. Run: {inc['run_id']}")
                            print(f"   Job: {inc['job_name']}")
                            print("   Output datasets:")
                            for name in inc["output_datasets"]:
                                print(f"   - {name}")
                            print()
                            print("   Affected downstream datasets:")
                            aff = inc["affected_datasets"]
                            if not aff:
                                print("   (none)")
                            else:
                                for a in aff:
                                    print(f"   - {a['name']} (distance: {a['distance']})")
                            print()
                        return 0
                    case "rank":
                        result = summarize_failed_runs(
                            store,
                            status=args.status,
                            since=args.since,
                            limit=None,
                        )
                        ranked = sorted(
                            result["incidents"],
                            key=lambda i: (i["blast_radius_score"], i["run_id"]),
                            reverse=True,
                        )
                        if args.limit is not None:
                            ranked = ranked[: int(args.limit)]

                        if args.json:
                            payload = {
                                "query_type": "incident_ranking",
                                "ranking_method": "affected_dataset_count",
                                "incidents": [
                                    {
                                        "rank": idx,
                                        "run_id": inc["run_id"],
                                        "job_name": inc["job_name"],
                                        "blast_radius_score": inc["blast_radius_score"],
                                        "severity": inc["severity"],
                                        "affected_count": inc["blast_radius_score"],
                                    }
                                    for idx, inc in enumerate(ranked, start=1)
                                ],
                            }
                            sys.stdout.write(dumps_json(payload))
                            return 0

                        status_label = args.status or "matching"
                        print(f"Ranked incidents by blast radius ({status_label} runs):\n")
                        if not ranked:
                            print("(none)")
                            return 0
                        for idx, inc in enumerate(ranked, start=1):
                            print(f"{idx}. {inc['run_id']} — {inc['job_name']}")
                            print(f"   Severity: {inc['severity']}")
                            print(f"   Blast radius score: {inc['blast_radius_score']}")
                            print(f"   Affected datasets: {inc['blast_radius_score']}")
                            print()
                        return 0
                    case _:
                        raise RuntimeError(
                            f"unhandled incidents command: {args.incidents_command!r}"
                        )
            case "upstream":
                if args.json:
                    items = lineage_upstream_results(store, args.dataset, depth=args.depth)
                    sys.stdout.write(dumps_json(upstream_payload(args.dataset, args.depth, items)))
                    return 0
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
                if args.json:
                    items = lineage_downstream_results(store, args.dataset, depth=args.depth)
                    sys.stdout.write(dumps_json(downstream_payload(args.dataset, args.depth, items)))
                    return 0
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
                if args.json:
                    items = lineage_impact_results(store, args.dataset, depth="all")
                    sys.stdout.write(dumps_json(impact_payload(args.dataset, items)))
                    return 0
                rows = impact_analysis(store, args.dataset)
                print(f"Downstream assets affected by {args.dataset}:\n")
                _print_bullets(rows)
                return 0
            case "graph":
                edges = collect_graph_edges(
                    store,
                    args.dataset,
                    direction=args.direction,
                    depth=args.depth,
                )
                match args.format:
                    case "text":
                        sys.stdout.write(format_edges_text(edges))
                    case "mermaid":
                        sys.stdout.write(format_edges_mermaid(edges))
                    case "dot":
                        sys.stdout.write(format_edges_dot(edges))
                    case _:
                        raise RuntimeError(f"unhandled format: {args.format!r}")
                return 0
            case "impact-run":
                analysis = analyze_run_impact(store, args.run_id)
                if args.json:
                    sys.stdout.write(dumps_json(run_impact_payload(analysis)))
                    return 0
                print(f"Run impact analysis for {analysis.external_run_id}\n")
                print(f"Job: {analysis.job_name}")
                print(f"Status: {analysis.status}")
                if analysis.error_message:
                    print(f"Error: {analysis.error_message}")
                print()
                print("Failed or affected output datasets:")
                _print_bullets(list(analysis.output_datasets))
                print()
                print("Downstream affected datasets:")
                _print_bullets([r.name for r in analysis.affected])
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


def _run_display_id(r: RunRecord) -> str:
    return r.external_run_id if r.external_run_id is not None else str(r.internal_run_id)


def _run_record_payload(r: RunRecord) -> dict:
    return {
        "run_id": _run_display_id(r),
        "job_name": r.job_name,
        "status": r.status,
        "started_at": r.started_at,
        "ended_at": r.ended_at,
    }


if __name__ == "__main__":
    raise SystemExit(main())
