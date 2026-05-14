"""Command-line interface for LineageHub."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lineagehub.db_path import default_db_path
from lineagehub.graph import (
    analyze_run_impact,
    collect_graph_edges,
    find_cycles,
    get_direct_downstream,
    get_direct_upstream,
    get_downstream,
    get_upstream,
    impact_analysis,
    lineage_downstream_results,
    lineage_impact_results,
    lineage_upstream_results,
)
from lineagehub.analysis import incident_ranking, summarize_failed_runs
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.output import (
    dataset_catalog_row,
    dataset_show_payload,
    downstream_payload,
    job_catalog_row,
    job_show_payload,
    dumps_json,
    format_edges_dot,
    format_edges_mermaid,
    format_edges_text,
    graph_cycles_payload,
    impact_payload,
    lineage_export_payload,
    run_impact_payload,
    run_list_row_payload,
    run_show_payload,
    upstream_payload,
)
from lineagehub.store import MetadataStore, RunRecord
from lineagehub.validation import validate_metadata


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

    p_export = sub.add_parser("export", help="Export stored metadata as JSON")
    export_sub = p_export.add_subparsers(dest="export_command", required=True)
    p_export_lineage = export_sub.add_parser(
        "lineage",
        help="Export datasets, jobs, lineage edges, and runs (loader-friendly shape)",
    )
    p_export_lineage.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format (default: json)",
    )

    p_export_incidents = export_sub.add_parser(
        "incidents",
        help="Export incident summary or ranking as JSON (same payloads as incidents summarize / rank)",
    )
    p_export_incidents.add_argument(
        "--ranked",
        action="store_true",
        help="Emit incident_ranking instead of incident_summary",
    )
    p_export_incidents.add_argument(
        "--status",
        default="failed",
        help="Run status filter (default: failed)",
    )
    p_export_incidents.add_argument(
        "--since",
        help="Only include runs with started_at >= SINCE (ISO-8601 string)",
    )
    p_export_incidents.add_argument(
        "--limit",
        type=int,
        help="Summary: max runs evaluated; ranked: max incidents returned",
    )
    p_export_incidents.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format (default: json)",
    )

    p_datasets = sub.add_parser("datasets", help="Dataset catalog")
    datasets_sub = p_datasets.add_subparsers(dest="datasets_command", required=True)

    p_datasets_list = datasets_sub.add_parser("list", help="List all datasets")
    p_datasets_list.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_datasets_show = datasets_sub.add_parser("show", help="Show one dataset and its lineage relationships")
    p_datasets_show.add_argument("dataset", help="Dataset name")
    p_datasets_show.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_jobs = sub.add_parser("jobs", help="Job catalog")
    jobs_sub = p_jobs.add_subparsers(dest="jobs_command", required=True)

    p_jobs_list = jobs_sub.add_parser("list", help="List all jobs")
    p_jobs_list.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_jobs_show = jobs_sub.add_parser("show", help="Show one job (inputs, outputs, runs)")
    p_jobs_show.add_argument("job", help="Job name")
    p_jobs_show.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

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

    p_runs_show = runs_sub.add_parser(
        "show",
        help="Show one run by external id or numeric internal id",
    )
    p_runs_show.add_argument(
        "run_id",
        help="External run id (e.g. run_001) or numeric internal row id",
    )
    p_runs_show.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

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

    p_graph = sub.add_parser("graph", help="Lineage graph export and cycle detection")
    graph_sub = p_graph.add_subparsers(dest="graph_command", required=True)

    p_graph_edges = graph_sub.add_parser("edges", help="Export lineage edges for a dataset")
    p_graph_edges.add_argument("dataset", help="Dataset name")
    p_graph_edges.add_argument(
        "--direction",
        choices=["upstream", "downstream", "both"],
        default="downstream",
        help="Which edges to include (default: downstream)",
    )
    p_graph_edges.add_argument("--depth", **depth_opt)
    p_graph_edges.add_argument(
        "--format",
        choices=["text", "mermaid", "dot"],
        default="text",
        help="Output format (default: text)",
    )

    p_graph_cycles = graph_sub.add_parser("cycles", help="List directed cycles in stored lineage")
    p_graph_cycles.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

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

    p_validate = sub.add_parser("validate", help="Validate metadata health (datasets, jobs, runs, lineage)")
    p_validate.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_doctor = sub.add_parser("doctor", help="Alias for validate")
    p_doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

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
            case "export":
                match args.export_command:
                    case "lineage":
                        if args.format != "json":
                            raise RuntimeError(f"unhandled export format: {args.format!r}")
                        sys.stdout.write(dumps_json(lineage_export_payload(store)))
                        return 0
                    case "incidents":
                        if args.format != "json":
                            raise RuntimeError(f"unhandled export format: {args.format!r}")
                        if args.ranked:
                            payload = incident_ranking(
                                store,
                                status=args.status,
                                since=args.since,
                                limit_runs=None,
                                limit_ranked=args.limit,
                            )
                        else:
                            payload = summarize_failed_runs(
                                store,
                                status=args.status,
                                since=args.since,
                                limit=args.limit,
                            )
                        sys.stdout.write(dumps_json(payload))
                        return 0
                    case _:
                        raise RuntimeError(f"unhandled export command: {args.export_command!r}")
            case "datasets":
                match args.datasets_command:
                    case "list":
                        rows = store.list_dataset_records()
                        if args.json:
                            payload = {
                                "query_type": "datasets_list",
                                "count": len(rows),
                                "datasets": [
                                    dataset_catalog_row(
                                        name=r.name,
                                        dataset_type=r.dataset_type,
                                        uri=r.uri,
                                        owner=r.owner,
                                        description=r.description,
                                        tags=r.tags,
                                        criticality=r.criticality,
                                        system=r.system,
                                    )
                                    for r in rows
                                ],
                            }
                            sys.stdout.write(dumps_json(payload))
                            return 0

                        print("Datasets:\n")
                        if not rows:
                            print("(none)")
                            return 0
                        for r in rows:
                            print(f"- {r.name}")
                            t = r.dataset_type if r.dataset_type is not None else "(none)"
                            u = r.uri if r.uri is not None else "(none)"
                            o = r.owner if r.owner is not None else "(none)"
                            c = r.criticality if r.criticality is not None else "(none)"
                            sy = r.system if r.system is not None else "(none)"
                            tag_line = ", ".join(r.tags) if r.tags else "(none)"
                            print(f"  Type: {t}")
                            print(f"  URI: {u}")
                            print(f"  Owner: {o}")
                            print(f"  Criticality: {c}")
                            print(f"  System: {sy}")
                            print(f"  Tags: {tag_line}")
                            print()
                        return 0
                    case "show":
                        ds = store.get_dataset_by_name(args.dataset)
                        if ds is None or ds.dataset_id is None:
                            raise ValueError(f"Unknown dataset: {args.dataset!r}")
                        upstream_items = lineage_upstream_results(store, args.dataset, depth="all")
                        downstream_items = lineage_downstream_results(store, args.dataset, depth="all")
                        producers = store.list_job_names_producing_dataset(ds.dataset_id)
                        consumers = store.list_job_names_consuming_dataset(ds.dataset_id)
                        if args.json:
                            sys.stdout.write(
                                dumps_json(
                                    dataset_show_payload(
                                        name=args.dataset,
                                        dataset_type=ds.dataset_type,
                                        uri=ds.uri,
                                        producer_jobs=producers,
                                        consumer_jobs=consumers,
                                        upstream=upstream_items,
                                        downstream=downstream_items,
                                        owner=ds.owner,
                                        description=ds.description,
                                        tags=ds.tags,
                                        criticality=ds.criticality,
                                        system=ds.system,
                                    )
                                )
                            )
                            return 0
                        _print_dataset_show(
                            name=args.dataset,
                            dataset_type=ds.dataset_type,
                            uri=ds.uri,
                            producer_jobs=producers,
                            consumer_jobs=consumers,
                            upstream_names=[x.name for x in upstream_items],
                            downstream_names=[x.name for x in downstream_items],
                            owner=ds.owner,
                            description=ds.description,
                            tags=ds.tags,
                            criticality=ds.criticality,
                            system=ds.system,
                        )
                        return 0
                    case _:
                        raise RuntimeError(f"unhandled datasets command: {args.datasets_command!r}")
            case "jobs":
                match args.jobs_command:
                    case "list":
                        rows = store.list_jobs()
                        if args.json:
                            payload = {
                                "query_type": "jobs_list",
                                "count": len(rows),
                                "jobs": [
                                    job_catalog_row(
                                        name=r.name, description=r.description, system=r.system
                                    )
                                    for r in rows
                                ],
                            }
                            sys.stdout.write(dumps_json(payload))
                            return 0

                        print("Jobs:\n")
                        if not rows:
                            print("(none)")
                            return 0
                        for r in rows:
                            print(f"- {r.name}")
                            d = r.description if r.description is not None else "(none)"
                            sy = r.system if r.system is not None else "(none)"
                            print(f"  Description: {d}")
                            print(f"  System: {sy}")
                            print()
                        return 0
                    case "show":
                        job = store.get_job_by_name(args.job)
                        if job is None or job.job_id is None:
                            raise ValueError(f"Unknown job: {args.job!r}")
                        inputs = store.list_input_dataset_names_for_job(job.job_id)
                        outputs = store.list_output_dataset_names_for_job(job.job_id)
                        latest = store.get_latest_run(args.job)
                        run_count = store.count_runs_for_job(job.job_id)
                        latest_json = run_list_row_payload(latest) if latest is not None else None
                        if args.json:
                            sys.stdout.write(
                                dumps_json(
                                    job_show_payload(
                                        name=job.name,
                                        description=job.description,
                                        system=job.system,
                                        inputs=inputs,
                                        outputs=outputs,
                                        latest_run=latest_json,
                                        run_count=run_count,
                                    )
                                )
                            )
                            return 0
                        _print_job_show(
                            name=job.name,
                            description=job.description,
                            system=job.system,
                            inputs=inputs,
                            outputs=outputs,
                            latest=latest,
                            run_count=run_count,
                        )
                        return 0
                    case _:
                        raise RuntimeError(f"unhandled jobs command: {args.jobs_command!r}")
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
                                "runs": [run_list_row_payload(r) for r in rows],
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
                    case "show":
                        rec = store.get_run_record_by_display_id(args.run_id)
                        if rec is None:
                            raise ValueError(f"Unknown run: {args.run_id!r}")
                        if args.json:
                            sys.stdout.write(dumps_json(run_show_payload(rec)))
                            return 0
                        print(f"Run: {_run_display_id(rec)}\n")
                        print(f"  Job: {rec.job_name}")
                        print(f"  Status: {rec.status}")
                        if rec.started_at is not None:
                            print(f"  Started: {rec.started_at}")
                        if rec.ended_at is not None:
                            print(f"  Ended: {rec.ended_at}")
                        if rec.error_message is not None:
                            print(f"  Error: {rec.error_message}")
                        return 0
                    case "latest":
                        latest = store.get_latest_run(args.job)
                        if args.json:
                            payload = {
                                "query_type": "latest_run",
                                "job_name": args.job,
                                "run": run_list_row_payload(latest) if latest is not None else None,
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
                        payload = incident_ranking(
                            store,
                            status=args.status,
                            since=args.since,
                            limit_runs=None,
                            limit_ranked=args.limit,
                        )
                        ranked = payload["incidents"]
                        if args.json:
                            sys.stdout.write(dumps_json(payload))
                            return 0

                        status_label = args.status or "matching"
                        print(f"Ranked incidents by blast radius ({status_label} runs):\n")
                        if not ranked:
                            print("(none)")
                            return 0
                        for row in ranked:
                            print(f"{row['rank']}. {row['run_id']} — {row['job_name']}")
                            print(f"   Severity: {row['severity']}")
                            print(f"   Blast radius score: {row['blast_radius_score']}")
                            print(f"   Affected datasets: {row['affected_count']}")
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
                match args.graph_command:
                    case "edges":
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
                    case "cycles":
                        cycles = find_cycles(store)
                        if args.json:
                            sys.stdout.write(dumps_json(graph_cycles_payload(cycles)))
                            return 0
                        if not cycles:
                            print("No lineage cycles detected.")
                        else:
                            print("Detected lineage cycles:\n")
                            for idx, cyc in enumerate(cycles, start=1):
                                print(f"{idx}. {' -> '.join(cyc)}")
                        return 0
                    case _:
                        raise RuntimeError(f"unhandled graph command: {args.graph_command!r}")
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
            case "validate" | "doctor":
                result = validate_metadata(store)
                if args.json:
                    sys.stdout.write(dumps_json(result))
                    return 1 if result["status"] == "fail" else 0
                _print_validation_text(result)
                return 1 if result["status"] == "fail" else 0
            case _:
                raise RuntimeError(f"unhandled command: {args.command!r}")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1


def _print_validation_text(result: dict) -> None:
    label = "PASS" if result["status"] == "pass" else "FAIL"
    print(f"Metadata validation: {label}\n")
    print("Warnings:")
    warnings = result.get("warnings") or []
    if not warnings:
        print("- None")
    else:
        for w in warnings:
            code = w.get("code", "?")
            msg = w.get("message", "")
            print(f"- {code}: {msg}")
    print()
    print("Errors:")
    errors = result.get("errors") or []
    if not errors:
        print("- None")
    else:
        for e in errors:
            code = e.get("code", "?")
            msg = e.get("message", "")
            print(f"- {code}: {msg}")


def _print_bullets(names: list[str]) -> None:
    if not names:
        print("(none)")
        return
    for name in names:
        print(f"- {name}")


def _run_display_id(r: RunRecord) -> str:
    return r.external_run_id if r.external_run_id is not None else str(r.internal_run_id)


def _bullets_or_none(names: list[str]) -> None:
    if not names:
        print("- None")
        return
    for n in names:
        print(f"- {n}")


def _print_job_show(
    *,
    name: str,
    description: str | None,
    system: str | None,
    inputs: list[str],
    outputs: list[str],
    latest: RunRecord | None,
    run_count: int,
) -> None:
    print(f"Job: {name}")
    sy = system if system is not None else "(none)"
    print(f"System: {sy}")
    if description is not None:
        print()
        print("Description:")
        print(description)
    print()
    print("Input datasets:")
    _bullets_or_none(inputs)
    print()
    print("Output datasets:")
    _bullets_or_none(outputs)
    print()
    print("Latest run:")
    if latest is None:
        print("(none)")
    else:
        print(f"- {_run_display_id(latest)}")
        print(f"  Status: {latest.status}")
    print()
    print(f"Recent runs: {run_count}")


def _print_dataset_show(
    *,
    name: str,
    dataset_type: str | None,
    uri: str | None,
    producer_jobs: list[str],
    consumer_jobs: list[str],
    upstream_names: list[str],
    downstream_names: list[str],
    owner: str | None = None,
    description: str | None = None,
    tags: tuple[str, ...] | None = None,
    criticality: str | None = None,
    system: str | None = None,
) -> None:
    t = dataset_type if dataset_type is not None else "(none)"
    u = uri if uri is not None else "(none)"
    o = owner if owner is not None else "(none)"
    c = criticality if criticality is not None else "(none)"
    sy = system if system is not None else "(none)"
    tag_line = ", ".join(tags) if tags else "(none)"
    print(f"Dataset: {name}")
    print(f"Type: {t}")
    print(f"URI: {u}")
    print(f"Owner: {o}")
    print(f"Criticality: {c}")
    print(f"System: {sy}")
    print(f"Tags: {tag_line}")
    if description is not None:
        print()
        print("Description:")
        print(description)
    print()
    print("Produced by:")
    _bullets_or_none(producer_jobs)
    print()
    print("Consumed by:")
    _bullets_or_none(consumer_jobs)
    print()
    print("Upstream datasets:")
    _bullets_or_none(upstream_names)
    print()
    print("Downstream datasets:")
    _bullets_or_none(downstream_names)


if __name__ == "__main__":
    raise SystemExit(main())
