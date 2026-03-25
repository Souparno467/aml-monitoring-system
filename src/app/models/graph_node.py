from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    user_id = Column(String(20), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    out_degree = Column(Integer, nullable=True, default=0)
    in_degree = Column(Integer, nullable=True, default=0)
    betweenness_centrality = Column(Numeric(12, 8), nullable=True)
    pagerank = Column(Numeric(14, 10), nullable=True)
    clustering_coefficient = Column(Numeric(12, 8), nullable=True)
    is_hub = Column(Boolean, nullable=True, default=False)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="graph_node")

    @property
    def total_degree(self) -> int:
        return int(self.in_degree or 0) + int(self.out_degree or 0)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "out_degree": self.out_degree,
            "in_degree": self.in_degree,
            "betweenness_centrality": float(self.betweenness_centrality or 0),
            "pagerank": float(self.pagerank or 0),
            "clustering_coefficient": float(self.clustering_coefficient or 0),
            "is_hub": bool(self.is_hub),
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }
