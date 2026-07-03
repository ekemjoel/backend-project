import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store


@pytest.fixture(autouse=True)
def clean_store():
    store._monitors.clear()
    store._alerts.clear()
    yield
    store._monitors.clear()
    store._alerts.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_register_monitor(client):
    resp = client.post(
        "/monitors",
        json={"id": "device-123", "timeout": 60, "alert_email": "admin@critmon.com"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["monitor"]["id"] == "device-123"
    assert body["monitor"]["status"] == "active"


def test_register_duplicate_monitor_returns_409(client):
    payload = {"id": "device-1", "timeout": 30, "alert_email": "a@b.com"}
    client.post("/monitors", json=payload)
    resp = client.post("/monitors", json=payload)
    assert resp.status_code == 409


def test_heartbeat_unknown_monitor_returns_404(client):
    resp = client.post("/monitors/ghost/heartbeat")
    assert resp.status_code == 404


def test_heartbeat_resets_timer(client):
    client.post(
        "/monitors",
        json={"id": "device-2", "timeout": 5, "alert_email": "a@b.com"},
    )
    resp = client.post("/monitors/device-2/heartbeat")
    assert resp.status_code == 200
    assert resp.json()["monitor"]["status"] == "active"


def test_pause_stops_timer_and_no_alert_fires(client):
    client.post(
        "/monitors",
        json={"id": "device-3", "timeout": 1, "alert_email": "a@b.com"},
    )
    resp = client.post("/monitors/device-3/pause")
    assert resp.status_code == 200
    assert resp.json()["monitor"]["status"] == "paused"

    time.sleep(1.5)

    detail = client.get("/monitors/device-3").json()
    assert detail["status"] == "paused"
    assert client.get("/alerts").json() == []


def test_heartbeat_unpauses_monitor(client):
    client.post(
        "/monitors",
        json={"id": "device-4", "timeout": 5, "alert_email": "a@b.com"},
    )
    client.post("/monitors/device-4/pause")
    resp = client.post("/monitors/device-4/heartbeat")
    assert resp.json()["monitor"]["status"] == "active"


def test_timeout_triggers_alert_and_down_status(client):
    client.post(
        "/monitors",
        json={"id": "device-5", "timeout": 0.3, "alert_email": "a@b.com"},
    )
    time.sleep(0.6)

    detail = client.get("/monitors/device-5").json()
    assert detail["status"] == "down"

    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["monitor_id"] == "device-5"


def test_invalid_payload_returns_422(client):
    resp = client.post(
        "/monitors",
        json={"id": "device-6", "timeout": -5, "alert_email": "not-an-email"},
    )
    assert resp.status_code == 422
