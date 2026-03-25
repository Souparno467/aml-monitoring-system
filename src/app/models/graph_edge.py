from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String

from app.db.base import Base


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), ForeignKey("users.user_id"), nullable=False)
    target = Column(String(20), ForeignKey("users.user_id"), nullable=False)
    txn_id = Column(String(20), ForeignKey("transactions.txn_id"), nullable=True)
    weight = Column(Numeric(18, 4), nullable=True)
    composite_risk_score = Column(Numeric(5, 4), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=True)
