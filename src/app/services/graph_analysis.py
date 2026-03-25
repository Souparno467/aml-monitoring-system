from __future__ import annotations


class GraphAnalysisService:
    def __init__(self) -> None:
        self._available = False
        try:
            import networkx as nx  # type: ignore

            self._nx = nx
            self._graph = nx.DiGraph()
            self._available = True
        except Exception:
            self._nx = None
            self._graph = None

    def add_transaction(
        self, sender_id: str, receiver_id: str, amount_usd: float, txn_id: str, risk_score: float = 0.0
    ) -> None:
        if not self._available:
            return
        if self._graph.has_edge(sender_id, receiver_id):
            self._graph[sender_id][receiver_id]["weight"] += amount_usd
        else:
            self._graph.add_edge(sender_id, receiver_id, weight=amount_usd, txn_ids=[txn_id], total_risk=risk_score)

    def compute_graph_score(self, user_id: str) -> float:
        if not self._available or user_id not in self._graph:
            return 0.0
        nx = self._nx
        bc = nx.betweenness_centrality(
            self._graph,
            k=min(200, self._graph.number_of_nodes()),
            normalized=True,
            weight="weight",
        )
        pr = nx.pagerank(self._graph, alpha=0.85, weight="weight")
        bc_score = min(bc.get(user_id, 0) * 10, 1.0)
        pr_score = min(pr.get(user_id, 0) * 1000, 1.0)
        return round(0.6 * bc_score + 0.4 * pr_score, 4)


graph_service = GraphAnalysisService()
