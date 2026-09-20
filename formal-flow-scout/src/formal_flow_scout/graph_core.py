"""Pure-Python graph core for cone-of-influence analysis.

Design goals (mirror the C++ "graph-core design" spec section):
* **Packed adjacency** - edges are stored in a single flat array grouped by
  source, with a CSR-style ``offsets`` index. This is cache-friendly (one
  sequential scan per node's fan-in) and avoids one heap object per node.
* **Stable node IDs** - IDs are dense ``0..N-1`` and assigned in first-seen
  order. All user-visible output is emitted in ascending ID order, so runs are
  bit-for-bit reproducible.
* **Deterministic ordering** - no reliance on set/dict iteration order for any
  emitted result; SCC ids follow Tarjan discovery order, which is deterministic
  given deterministic adjacency.
* **Incremental queries** - the CSR is built once; each property query is an
  independent BFS that reuses the immutable adjacency.

Data-layout / cache rationale is documented in ARCHITECTURE.md.

Edge direction convention: an edge ``src -> dst`` means "signal ``src`` depends
on (is driven by) signal ``dst``". Therefore backward cone-of-influence from a
property seed is a *forward* traversal over this graph, following fan-in.
"""

from __future__ import annotations

from array import array
from collections.abc import Iterable

from .models import DependencyGraph, EdgeKind, GraphNode, NodeKind

# Edge kinds that carry data/control dependency for COI purposes. HIER edges are
# structural annotations and are traversed too (they represent the same signal
# on both sides of a boundary), but we keep the kind so partitioning can reason
# about boundaries. CLOCK/RESET edges are traversed only during the sequential
# expansion phase so that clock/reset trees do not pollute the combinational COI
# unless explicitly requested.
_COMB_EDGE_KINDS = frozenset({EdgeKind.COMB, EdgeKind.HIER})
_SEQ_EDGE_KINDS = frozenset({EdgeKind.SEQ})
_CTRL_EDGE_KINDS = frozenset({EdgeKind.CLOCK, EdgeKind.RESET})


class PackedGraph:
    """Immutable CSR representation of a :class:`DependencyGraph`.

    Attributes are intentionally flat arrays for locality:
    * ``offsets[i] .. offsets[i+1]`` index ``adj``/``adj_kind`` for node ``i``.
    * ``adj[j]`` is a destination node id; ``adj_kind[j]`` its :class:`EdgeKind`
      value (stored as a small int).
    """

    __slots__ = (
        "n",
        "nodes",
        "name_to_id",
        "offsets",
        "adj",
        "adj_kind",
        "kinds",
        "_kind_lookup",
    )

    def __init__(self, graph: DependencyGraph) -> None:
        nodes = sorted(graph.nodes, key=lambda x: x.node_id)
        n = len(nodes)
        # Validate dense 0..N-1 ids so the CSR index is a direct lookup.
        for expected, node in enumerate(nodes):
            if node.node_id != expected:
                raise ValueError(
                    f"node ids must be dense 0..N-1; got {node.node_id} at position {expected}"
                )
        self.n = n
        self.nodes: list[GraphNode] = nodes
        self.name_to_id: dict[str, int] = {node.name: node.node_id for node in nodes}
        self.kinds: list[NodeKind] = [node.kind for node in nodes]

        # Small-int encoding for edge kinds (stored in a compact 'B' array).
        self._kind_lookup = list(EdgeKind)
        kind_to_int = {k: i for i, k in enumerate(self._kind_lookup)}

        # Count degree per source for the CSR offsets.
        degree = array("i", [0]) * 0  # placeholder to satisfy type; rebuilt below
        degree = array("i", [0] * n)
        for edge in graph.edges:
            if not (0 <= edge.src < n) or not (0 <= edge.dst < n):
                raise ValueError(f"edge references out-of-range node: {edge}")
            degree[edge.src] += 1

        offsets = array("i", [0] * (n + 1))
        for i in range(n):
            offsets[i + 1] = offsets[i] + degree[i]
        total = offsets[n]

        adj = array("i", [0] * total)
        adj_kind = array("B", [0] * total)
        cursor = array("i", offsets[:n])  # writable copy of the start offsets
        # Emit edges in stable input order so ties resolve deterministically.
        for edge in graph.edges:
            pos = cursor[edge.src]
            adj[pos] = edge.dst
            adj_kind[pos] = kind_to_int[edge.kind]
            cursor[edge.src] = pos + 1
        # Sort each node's neighbour slice by (dst, kind) for deterministic
        # output regardless of input edge ordering.
        for i in range(n):
            start, end = offsets[i], offsets[i + 1]
            if end - start > 1:
                pairs = sorted(
                    zip(adj[start:end], adj_kind[start:end], strict=True),
                    key=lambda p: (p[0], p[1]),
                )
                for k, (d, kk) in enumerate(pairs):
                    adj[start + k] = d
                    adj_kind[start + k] = kk

        self.offsets = offsets
        self.adj = adj
        self.adj_kind = adj_kind

    # -- neighbour access ---------------------------------------------------- #

    def neighbours(self, node_id: int) -> Iterable[tuple[int, EdgeKind]]:
        """Yield ``(dst, kind)`` for every fan-in edge of ``node_id``."""
        start, end = self.offsets[node_id], self.offsets[node_id + 1]
        for j in range(start, end):
            yield self.adj[j], self._kind_lookup[self.adj_kind[j]]

    def id_of(self, name: str) -> int | None:
        return self.name_to_id.get(name)

    # -- COI traversal ------------------------------------------------------- #

    def backward_coi(
        self,
        seeds: Iterable[int],
        *,
        combinational_only: bool,
        include_control: bool,
    ) -> set[int]:
        """Return the set of node ids reachable from ``seeds`` via fan-in.

        This is a *sound over-approximation* of the structural cone of
        influence: every signal that can (structurally) affect a seed is
        included. It never drops a real dependency, so it cannot make a proof
        unsound by omission (see ARCHITECTURE.md).

        * ``combinational_only=True``  - stop at register boundaries (do not
          cross ``SEQ`` edges). This is the *combinational* COI.
        * ``combinational_only=False`` - also cross ``SEQ`` edges (sequential
          expansion through state elements).
        * ``include_control`` - also follow CLOCK/RESET edges.
        """
        if combinational_only:
            allowed = set(_COMB_EDGE_KINDS)
        else:
            allowed = set(_COMB_EDGE_KINDS) | set(_SEQ_EDGE_KINDS)
        if include_control:
            allowed |= set(_CTRL_EDGE_KINDS)

        visited: set[int] = set()
        # Use a list as a stack; iterative to avoid recursion limits on deep RTL.
        stack = [s for s in sorted(set(seeds)) if 0 <= s < self.n]
        visited.update(stack)
        while stack:
            cur = stack.pop()
            for dst, kind in self.neighbours(cur):
                if kind in allowed and dst not in visited:
                    visited.add(dst)
                    stack.append(dst)
        return visited

    def tarjan_scc(self, subset: set[int] | None = None) -> list[list[int]]:
        """Tarjan strongly-connected-components.

        Iterative (explicit stack) so it handles deep graphs. Only ``COMB``,
        ``SEQ`` and ``HIER`` edges participate - CLOCK/RESET are control fanout,
        not feedback. If ``subset`` is given, the SCC search is restricted to
        those nodes (used to analyse the COI in isolation).

        Returns components as sorted node-id lists, ordered by ascending minimum
        node id for deterministic output.
        """
        allowed = _COMB_EDGE_KINDS | _SEQ_EDGE_KINDS
        in_subset = (lambda x: True) if subset is None else (lambda x: x in subset)
        node_range = range(self.n) if subset is None else sorted(subset)

        index_counter = 0
        indices: dict[int, int] = {}
        lowlink: dict[int, int] = {}
        on_stack: set[int] = set()
        scc_stack: list[int] = []
        result: list[list[int]] = []

        for root in node_range:
            if root in indices:
                continue
            # Explicit DFS stack of (node, neighbour-iterator-position).
            work: list[tuple[int, int]] = [(root, 0)]
            neigh_cache: dict[int, list[int]] = {}
            while work:
                v, pi = work[-1]
                if pi == 0:
                    indices[v] = lowlink[v] = index_counter
                    index_counter += 1
                    scc_stack.append(v)
                    on_stack.add(v)
                    neigh_cache[v] = [
                        d
                        for d, k in self.neighbours(v)
                        if k in allowed and in_subset(d)
                    ]
                neighs = neigh_cache[v]
                if pi < len(neighs):
                    work[-1] = (v, pi + 1)
                    w = neighs[pi]
                    if w not in indices:
                        work.append((w, 0))
                    elif w in on_stack and indices[w] < lowlink[v]:
                        lowlink[v] = indices[w]
                else:
                    # Done with v: propagate lowlink to parent, maybe close SCC.
                    work.pop()
                    if work:
                        parent = work[-1][0]
                        if lowlink[v] < lowlink[parent]:
                            lowlink[parent] = lowlink[v]
                    if lowlink[v] == indices[v]:
                        comp: list[int] = []
                        while True:
                            w = scc_stack.pop()
                            on_stack.discard(w)
                            comp.append(w)
                            if w == v:
                                break
                        result.append(sorted(comp))
        result.sort(key=lambda c: c[0])
        return result

    def has_self_loop(self, node_id: int) -> bool:
        allowed = _COMB_EDGE_KINDS | _SEQ_EDGE_KINDS
        return any(d == node_id and k in allowed for d, k in self.neighbours(node_id))
