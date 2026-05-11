"""Dataset lineage graph: upstream, downstream, and impact (transitive closure)."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Literal

from lineagehub.models import LineageEdge, LineageResult, RunImpactAnalysis, RunImpactRow
from lineagehub.store import MetadataStore

DepthSpec = Literal["direct", "all"]
DirectionSpec = Literal["upstream", "downstream", "both"]


def get_direct_upstream(store: MetadataStore, dataset_name: str) -> list[str]:
    """Immediate upstream datasets (one hop backward), sorted by name."""
    start = _dataset_id_or_raise(store, dataset_name)
    backward = _build_backward_adjacency(store.list_lineage_edges())
    id_to_name = _id_to_name_map(store)
    parents = sorted(set(backward.get(start, [])), key=lambda i: id_to_name[i])
    return [id_to_name[i] for i in parents]


def get_upstream(store: MetadataStore, dataset_name: str) -> list[str]:
    """Transitive upstream datasets (dependencies), breadth-first, nearest first."""
    start = _dataset_id_or_raise(store, dataset_name)
    backward = _build_backward_adjacency(store.list_lineage_edges())
    ids = _bfs_general(backward, start)
    return _ids_to_names(store, ids)


def get_direct_downstream(store: MetadataStore, dataset_name: str) -> list[str]:
    """Immediate downstream datasets (one hop forward), sorted by name."""
    start = _dataset_id_or_raise(store, dataset_name)
    forward = _build_forward_adjacency(store.list_lineage_edges())
    id_to_name = _id_to_name_map(store)
    children = sorted(set(forward.get(start, [])), key=lambda i: id_to_name[i])
    return [id_to_name[i] for i in children]


def get_downstream(store: MetadataStore, dataset_name: str) -> list[str]:
    """Transitive downstream datasets (consumers), breadth-first, nearest first."""
    start = _dataset_id_or_raise(store, dataset_name)
    forward = _build_forward_adjacency(store.list_lineage_edges())
    ids = _bfs_general(forward, start)
    return _ids_to_names(store, ids)


def impact_analysis(store: MetadataStore, dataset_name: str) -> list[str]:
    """Datasets affected if ``dataset_name`` fails or goes stale (downstream closure)."""
    return get_downstream(store, dataset_name)


def find_cycles(store: MetadataStore) -> list[list[str]]:
    """Return directed cycles as name lists ``[v0, v1, ..., v0]`` (first vertex repeated at end).

    Deterministic: neighbors are visited in dataset name order; reported cycles use a canonical
    rotation (lexicographically smallest rotation of the vertex sequence) then sorted by that tuple.
    """
    edges = store.list_lineage_edges()
    if not edges:
        return []

    id_to_name = _id_to_name_map(store)
    forward = _build_forward_adjacency(edges)
    for uid in list(forward.keys()):
        forward[uid] = sorted(set(forward[uid]), key=lambda i: id_to_name[i])

    nodes: set[int] = set()
    for e in edges:
        nodes.add(e.upstream_dataset_id)
        nodes.add(e.downstream_dataset_id)

    color: dict[int, int] = {}
    WHITE, GRAY, BLACK = 0, 1, 2
    stack: list[int] = []
    canon_seen: set[tuple[str, ...]] = set()
    cycles_out: list[list[str]] = []

    def canonical_closed_path(names: list[str]) -> tuple[str, ...]:
        if len(names) < 2 or names[0] != names[-1]:
            raise ValueError("expected closed path with matching endpoints")
        core = names[:-1]
        n = len(core)
        best = min(tuple(core[i:] + core[:i]) for i in range(n))
        return best + (best[0],)

    def dfs_visit(u: int) -> None:
        color[u] = GRAY
        stack.append(u)
        for v in forward.get(u, []):
            cv = color.get(v, WHITE)
            if cv == WHITE:
                dfs_visit(v)
            elif cv == GRAY:
                idx = stack.index(v)
                path_ids = stack[idx:] + [v]
                names = [id_to_name[i] for i in path_ids]
                key = canonical_closed_path(names)
                if key not in canon_seen:
                    canon_seen.add(key)
                    cycles_out.append(list(key))
        stack.pop()
        color[u] = BLACK

    for start in sorted(nodes, key=lambda i: id_to_name[i]):
        if color.get(start, WHITE) == WHITE:
            dfs_visit(start)

    cycles_out.sort(key=lambda c: tuple(c))
    return cycles_out


def lineage_upstream_results(
    store: MetadataStore, dataset_name: str, *, depth: DepthSpec
) -> list[LineageResult]:
    """Upstream datasets with hop distance from ``dataset_name``."""
    start = _dataset_id_or_raise(store, dataset_name)
    id_to_name = _id_to_name_map(store)
    backward = _build_backward_adjacency(store.list_lineage_edges())
    if depth == "direct":
        parents = sorted(set(backward.get(start, [])), key=lambda i: id_to_name[i])
        return [LineageResult(name=id_to_name[i], distance=1) for i in parents]
    pairs = _bfs_with_distance(backward, start)
    return [LineageResult(name=id_to_name[i], distance=d) for i, d in pairs]


def lineage_downstream_results(
    store: MetadataStore, dataset_name: str, *, depth: DepthSpec
) -> list[LineageResult]:
    """Downstream datasets with hop distance from ``dataset_name``."""
    start = _dataset_id_or_raise(store, dataset_name)
    id_to_name = _id_to_name_map(store)
    forward = _build_forward_adjacency(store.list_lineage_edges())
    if depth == "direct":
        children = sorted(set(forward.get(start, [])), key=lambda i: id_to_name[i])
        return [LineageResult(name=id_to_name[i], distance=1) for i in children]
    pairs = _bfs_with_distance(forward, start)
    return [LineageResult(name=id_to_name[i], distance=d) for i, d in pairs]


def lineage_impact_results(
    store: MetadataStore, dataset_name: str, *, depth: DepthSpec = "all"
) -> list[LineageResult]:
    """Dataset-level impact as downstream closure with distances."""
    return lineage_downstream_results(store, dataset_name, depth=depth)


def analyze_run_impact(store: MetadataStore, external_run_id: str) -> RunImpactAnalysis:
    """Transitive downstream impact starting from the job's output datasets for one run."""
    ctx = store.fetch_run_context_by_external_id(external_run_id)
    if ctx is None:
        raise ValueError(f"Unknown run: {external_run_id!r}")

    output_ids = store.list_output_dataset_ids_for_job(ctx.job_id)
    id_to_name = _id_to_name_map(store)
    outputs_sorted = tuple(sorted(id_to_name[i] for i in output_ids))
    forward = _build_forward_adjacency(store.list_lineage_edges())
    seed_ids = set(output_ids)

    queue: deque[tuple[int, int, str]] = deque()
    for sid in sorted(output_ids, key=lambda i: id_to_name[i]):
        sname = id_to_name[sid]
        for nid in sorted(set(forward.get(sid, [])), key=lambda i: id_to_name[i]):
            queue.append((nid, 1, sname))

    visited: set[int] = set(seed_ids)
    affected_list: list[RunImpactRow] = []

    while queue:
        nid, dist, src_name = queue.popleft()
        if nid in visited:
            continue
        visited.add(nid)
        affected_list.append(
            RunImpactRow(name=id_to_name[nid], distance=dist, source_output=src_name)
        )
        for nxt in sorted(set(forward.get(nid, [])), key=lambda i: id_to_name[i]):
            if nxt not in visited:
                queue.append((nxt, dist + 1, src_name))

    return RunImpactAnalysis(
        external_run_id=external_run_id,
        job_name=ctx.job_name,
        status=ctx.status,
        error_message=ctx.error_message,
        output_datasets=outputs_sorted,
        affected=tuple(affected_list),
    )


def collect_graph_edges(
    store: MetadataStore,
    dataset_name: str,
    *,
    direction: DirectionSpec = "downstream",
    depth: DepthSpec = "all",
) -> list[tuple[str, str]]:
    """Directed edges ``(upstream_name, downstream_name)`` for export."""
    root = _dataset_id_or_raise(store, dataset_name)
    edges_raw = store.list_lineage_edges()
    forward = _build_forward_adjacency(edges_raw)
    backward = _build_backward_adjacency(edges_raw)
    id_to_name = _id_to_name_map(store)

    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []

    def add_edge(uid: int, vid: int) -> None:
        key = (id_to_name[uid], id_to_name[vid])
        if key not in seen:
            seen.add(key)
            ordered.append(key)

    if direction in ("downstream", "both"):
        if depth == "direct":
            for v in sorted(set(forward.get(root, [])), key=lambda i: id_to_name[i]):
                add_edge(root, v)
        else:
            closure = {root} | set(_bfs_general(forward, root))
            for e in edges_raw:
                if e.upstream_dataset_id in closure and e.downstream_dataset_id in closure:
                    add_edge(e.upstream_dataset_id, e.downstream_dataset_id)

    if direction in ("upstream", "both"):
        if depth == "direct":
            for u in sorted(set(backward.get(root, [])), key=lambda i: id_to_name[i]):
                add_edge(u, root)
        else:
            closure = {root} | set(_bfs_general(backward, root))
            for e in edges_raw:
                if e.upstream_dataset_id in closure and e.downstream_dataset_id in closure:
                    add_edge(e.upstream_dataset_id, e.downstream_dataset_id)

    ordered.sort(key=lambda t: (t[0], t[1]))
    return ordered


def _dataset_id_or_raise(store: MetadataStore, dataset_name: str) -> int:
    did = store.get_dataset_id_by_name(dataset_name)
    if did is None:
        raise ValueError(f"Unknown dataset: {dataset_name!r}")
    return did


def _build_forward_adjacency(edges: list[LineageEdge]) -> dict[int, list[int]]:
    adj: dict[int, list[int]] = defaultdict(list)
    for e in edges:
        adj[e.upstream_dataset_id].append(e.downstream_dataset_id)
    return adj


def _build_backward_adjacency(edges: list[LineageEdge]) -> dict[int, list[int]]:
    adj: dict[int, list[int]] = defaultdict(list)
    for e in edges:
        adj[e.downstream_dataset_id].append(e.upstream_dataset_id)
    return adj


def _bfs_general(adj: dict[int, list[int]], start_id: int) -> list[int]:
    """Breadth-first from neighbors of ``start_id``; returns visited IDs in visit order."""
    return [i for i, _ in _bfs_with_distance(adj, start_id)]


def _bfs_with_distance(adj: dict[int, list[int]], start_id: int) -> list[tuple[int, int]]:
    """Breadth-first from ``start_id``; returns ``(node_id, distance)`` in visit order."""
    out: list[tuple[int, int]] = []
    visited: set[int] = set()
    queue: deque[tuple[int, int]] = deque()
    for nxt in adj.get(start_id, []):
        queue.append((nxt, 1))
    while queue:
        cur, dist = queue.popleft()
        if cur in visited:
            continue
        visited.add(cur)
        out.append((cur, dist))
        for nxt in adj.get(cur, []):
            if nxt not in visited:
                queue.append((nxt, dist + 1))
    return out


def _id_to_name_map(store: MetadataStore) -> dict[int, str]:
    return {d.dataset_id: d.name for d in store.list_datasets() if d.dataset_id is not None}


def _ids_to_names(store: MetadataStore, ids: list[int]) -> list[str]:
    id_to_name = _id_to_name_map(store)
    return [id_to_name[i] for i in ids]

