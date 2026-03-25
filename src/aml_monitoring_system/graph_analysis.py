"""
Graph Analysis Service
----------------------
Builds a directed transaction graph using NetworkX and computes:
  - Betweenness centrality
  - PageRank
  - Circular money movement detection
  - Hub-and-spoke laundering patterns
  - Community detection (Louvain / greedy modularity)
"""
from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import Optional
import networkx as nx
import structlog

logger = structlog.get_logger(__name__)


class GraphAnalysisService:
    def __init__(self):
        self._graph: nx.DiGraph = nx.DiGraph()
        self._user_scores: dict[str, float] = {}

    # ── Graph Construction ────────────────────────────────────────────────────

    def add_transaction(
        self,
        sender_id  : str,
        receiver_id: str,
        amount_usd : float,
        txn_id     : str,
        risk_score : float = 0.0,
    ) -> None:
        if self._graph.has_edge(sender_id, receiver_id):
            self._graph[sender_id][receiver_id]["weight"]     += amount_usd
            self._graph[sender_id][receiver_id]["txn_count"]  += 1
            self._graph[sender_id][receiver_id]["total_risk"] += risk_score
        else:
            self._graph.add_edge(
                sender_id, receiver_id,
                weight=amount_usd,
                txn_count=1,
                txn_ids=[txn_id],
                total_risk=risk_score,
            )

    def build_from_records(self, records: list[dict]) -> None:
        """Bulk load from list of transaction dicts."""
        self._graph.clear()
        for r in records:
            self.add_transaction(
                sender_id   = r["sender_id"],
                receiver_id = r["receiver_id"],
                amount_usd  = float(r.get("amount_usd", 0)),
                txn_id      = r["txn_id"],
                risk_score  = float(r.get("composite_risk_score", 0)),
            )
        logger.info("Graph built", nodes=self._graph.number_of_nodes(), edges=self._graph.number_of_edges())

    # ── Centrality Metrics ────────────────────────────────────────────────────

    def compute_betweenness(self, k: Optional[int] = None) -> dict[str, float]:
        """Approximate betweenness centrality. k = sample nodes for speed."""
        return nx.betweenness_centrality(self._graph, k=k, normalized=True, weight="weight")

    def compute_pagerank(self, alpha: float = 0.85) -> dict[str, float]:
        """PageRank on weighted transaction graph."""
        return nx.pagerank(self._graph, alpha=alpha, weight="weight")

    def compute_in_degree(self) -> dict[str, int]:
        return dict(self._graph.in_degree())

    def compute_out_degree(self) -> dict[str, int]:
        return dict(self._graph.out_degree())

    # ── Pattern Detection ─────────────────────────────────────────────────────

    def detect_cycles(self, max_length: int = 5) -> list[list[str]]:
        """
        Find simple cycles (potential round-trip / circular laundering).
        Filters cycles shorter than max_length to reduce noise.
        """
        cycles = []
        try:
            for cycle in nx.simple_cycles(self._graph):
                if 2 <= len(cycle) <= max_length:
                    cycles.append(cycle)
        except nx.NetworkXError as e:
            logger.warning("Cycle detection error", error=str(e))
        return cycles

    def detect_high_centrality_nodes(self, top_n: int = 20) -> list[dict]:
        """Return top-N nodes by betweenness centrality — potential money mules."""
        bc = self.compute_betweenness(k=min(500, self._graph.number_of_nodes()))
        sorted_nodes = sorted(bc.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [{"user_id": uid, "betweenness": round(score, 6)} for uid, score in sorted_nodes]

    def detect_hub_and_spoke(self, in_degree_threshold: int = 10) -> list[dict]:
        """
        Hub-and-spoke pattern: one hub receives from many nodes (spokes)
        and rapidly redistributes — classic placement layer.
        """
        hubs = []
        for node in self._graph.nodes():
            in_deg  = self._graph.in_degree(node)
            out_deg = self._graph.out_degree(node)
            if in_deg >= in_degree_threshold and out_deg >= 3:
                neighbours_in  = list(self._graph.predecessors(node))
                neighbours_out = list(self._graph.successors(node))
                # Overlap between in/out neighbours suggests pass-through
                overlap_ratio = len(set(neighbours_in) & set(neighbours_out)) / max(len(neighbours_in), 1)
                hubs.append({
                    "user_id"       : node,
                    "in_degree"     : in_deg,
                    "out_degree"    : out_deg,
                    "overlap_ratio" : round(overlap_ratio, 3),
                    "suspicious"    : overlap_ratio > 0.3,
                })
        return hubs

    def detect_communities(self) -> dict[str, int]:
        """Community detection using greedy modularity (undirected projection)."""
        undirected = self._graph.to_undirected()
        communities = nx.community.greedy_modularity_communities(undirected, weight="weight")
        node_to_community = {}
        for i, community in enumerate(communities):
            for node in community:
                node_to_community[node] = i
        return node_to_community

    # ── Per-Node Graph Score ──────────────────────────────────────────────────

    def compute_graph_score(self, user_id: str) -> float:
        """
        Composite graph anomaly score for a single user (0-1).
        Combines normalised betweenness, pagerank, and cycle membership.
        """
        if user_id not in self._graph:
            return 0.0

        bc    = self.compute_betweenness(k=min(200, self._graph.number_of_nodes()))
        pr    = self.compute_pagerank()
        cycles = self.detect_cycles()

        in_cycle = any(user_id in c for c in cycles)
        bc_score = min(bc.get(user_id, 0) * 10, 1.0)
        pr_score = min(pr.get(user_id, 0) * 1000, 1.0)

        score = 0.4 * bc_score + 0.3 * pr_score + 0.3 * float(in_cycle)
        return round(score, 4)

    # ── Summary ───────────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        cycles = self.detect_cycles()
        return {
            "total_nodes"       : self._graph.number_of_nodes(),
            "total_edges"       : self._graph.number_of_edges(),
            "total_cycles"      : len(cycles),
            "density"           : round(nx.density(self._graph), 6),
            "avg_in_degree"     : round(
                sum(d for _, d in self._graph.in_degree()) / max(self._graph.number_of_nodes(), 1), 2
            ),
        }


graph_service = GraphAnalysisService()
