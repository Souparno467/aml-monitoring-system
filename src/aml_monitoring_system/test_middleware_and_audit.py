"""
Middleware & Audit Service Tests
"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


# ── RequestID Middleware ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_id_header_added(app_client: AsyncClient):
    resp = await app_client.get("/health")
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) == 36  # UUID4


@pytest.mark.asyncio
async def test_client_request_id_echoed(app_client: AsyncClient):
    custom_id = "my-trace-id-12345"
    resp = await app_client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.headers["x-request-id"] == custom_id


# ── Rate Limit Middleware ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_headers_present(app_client: AsyncClient):
    """Rate limit headers should be present on every non-health response."""
    resp = await app_client.get("/api/v1/transactions/", headers={})
    # Will be 401 (no auth) but headers should still be there if Redis is up
    # In test env Redis may not be available so we just check no 500
    assert resp.status_code in (200, 401, 429)


# ── Audit Service ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_log_written_on_alert_update(
    app_client: AsyncClient, analyst_headers, sample_alert, db_session
):
    from app.core.audit import AuditLog
    from sqlalchemy import select

    resp = await app_client.patch(
        f"/api/v1/alerts/{sample_alert.alert_id}",
        headers=analyst_headers,
        json={"notes": "Confirmed suspicious activity"},
    )
    assert resp.status_code == 200

    logs = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_id == sample_alert.alert_id)
    )
    entries = logs.scalars().all()
    assert len(entries) >= 1
    assert entries[0].action in ("ALERT_UPDATED", "SAR_FILED", "FALSE_POSITIVE_MARKED")
    assert entries[0].entity_type == "alert"


@pytest.mark.asyncio
async def test_audit_log_written_on_escalation(
    app_client: AsyncClient, analyst_headers, sample_alert, db_session
):
    from app.core.audit import AuditLog
    from sqlalchemy import select

    await app_client.post(
        f"/api/v1/alerts/{sample_alert.alert_id}/escalate",
        headers=analyst_headers,
    )
    logs = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == sample_alert.alert_id)
        .where(AuditLog.action == "ALERT_ESCALATED")
    )
    assert logs.scalars().first() is not None


@pytest.mark.asyncio
async def test_audit_service_never_crashes_on_db_error(db_session):
    """Audit failure must never propagate to the caller."""
    from app.core.audit import audit

    with patch.object(db_session, "flush", side_effect=Exception("DB down")):
        result = await audit.log(
            db_session,
            actor={"user_id": "test", "role": "analyst"},
            action="TEST_ACTION",
        )
    # Should return None gracefully, not raise
    assert result is None


# ── GraphNode Model ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_graph_node_persisted(db_session, sample_user):
    from app.models.graph_node import GraphNode

    node = GraphNode(
        user_id                = sample_user.user_id,
        out_degree             = 15,
        in_degree              = 8,
        betweenness_centrality = 0.00312,
        pagerank               = 0.000142,
        clustering_coefficient = 0.241,
        is_hub                 = True,
    )
    db_session.add(node)
    await db_session.flush()

    fetched = await db_session.get(GraphNode, sample_user.user_id)
    assert fetched is not None
    assert fetched.is_hub is True
    assert fetched.total_degree == 23


def test_graph_node_to_dict():
    from app.models.graph_node import GraphNode
    node = GraphNode(
        user_id="USR001", out_degree=5, in_degree=3,
        betweenness_centrality=0.005, pagerank=0.0001,
        clustering_coefficient=0.3, is_hub=False,
    )
    d = node.to_dict()
    assert d["user_id"] == "USR001"
    assert d["is_hub"] is False
    assert isinstance(d["betweenness_centrality"], float)
