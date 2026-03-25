"""Alert API Tests — lifecycle from Open → Escalated → Closed"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_alerts(app_client: AsyncClient, sample_alert):
    resp = await app_client.get("/api/v1/alerts/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["results"][0]["alert_id"] is not None


@pytest.mark.asyncio
async def test_get_alert_by_id(app_client: AsyncClient, sample_alert):
    resp = await app_client.get(f"/api/v1/alerts/{sample_alert.alert_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["alert_id"] == sample_alert.alert_id
    assert data["severity"] == "HIGH"
    assert data["alert_status"] == "Open"


@pytest.mark.asyncio
async def test_get_alert_not_found(app_client: AsyncClient):
    resp = await app_client.get("/api/v1/alerts/NONEXISTENT_ALERT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_alert_status(app_client: AsyncClient, sample_alert):
    resp = await app_client.patch(
        f"/api/v1/alerts/{sample_alert.alert_id}",
        json={"alert_status": "Under Review", "notes": "Reviewing transaction history"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["alert_status"] == "Under Review"
    assert data["notes"] == "Reviewing transaction history"


@pytest.mark.asyncio
async def test_close_alert_sets_resolved_at(app_client: AsyncClient, sample_alert):
    resp = await app_client.patch(
        f"/api/v1/alerts/{sample_alert.alert_id}",
        json={"alert_status": "Closed-False Positive", "false_positive": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["alert_status"] == "Closed-False Positive"
    assert data["false_positive"] is True
    assert data["alert_resolved_at"] is not None
    assert data["resolution_time_hours"] is not None


@pytest.mark.asyncio
async def test_file_sar(app_client: AsyncClient, sample_alert):
    resp = await app_client.patch(
        f"/api/v1/alerts/{sample_alert.alert_id}",
        json={"alert_status": "Closed-SAR Filed", "sar_filed": True},
    )
    assert resp.status_code == 200
    assert resp.json()["sar_filed"] is True


@pytest.mark.asyncio
async def test_escalate_alert(app_client: AsyncClient, sample_alert):
    resp = await app_client.post(f"/api/v1/alerts/{sample_alert.alert_id}/escalate")
    assert resp.status_code == 200
    assert resp.json()["alert_status"] == "Escalated"


@pytest.mark.asyncio
async def test_filter_alerts_by_severity(app_client: AsyncClient, sample_alert):
    resp = await app_client.get("/api/v1/alerts/?severity=HIGH")
    assert resp.status_code == 200
    for alert in resp.json()["results"]:
        assert alert["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_filter_alerts_by_user(app_client: AsyncClient, sample_alert):
    resp = await app_client.get(f"/api/v1/alerts/?user_id={sample_alert.user_id}")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
