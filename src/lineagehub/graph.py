"""Dataset lineage graph: upstream, downstream, and impact (transitive closure)."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Literal

from lineagehub.models import LineageEdge, LineageResult
from lineagehub.store import MetadataStore

DepthSpec = Literal["direct", "all"]


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

