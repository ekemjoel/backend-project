from typing import List

from fastapi import APIRouter, HTTPException, status

from app.models import (
    AlertRecord,
    MessageResponse,
    MonitorCreateRequest,
    MonitorResponse,
)
from app.store import (
    Monitor,
    MonitorAlreadyExistsError,
    MonitorNotFoundError,
    store,
)

router = APIRouter()


def _to_response(monitor: Monitor) -> MonitorResponse:
    return MonitorResponse(
        id=monitor.id,
        status=monitor.status,
        timeout=monitor.timeout,
        alert_email=monitor.alert_email,
        created_at=monitor.created_at,
        last_heartbeat_at=monitor.last_heartbeat_at,
        seconds_remaining=monitor.seconds_remaining(),
    )


@router.post(
    "/monitors", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
def create_monitor(payload: MonitorCreateRequest):
    try:
        monitor = store.create(payload.id, payload.timeout, payload.alert_email)
    except MonitorAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Monitor '{payload.id}' already exists",
        )
    return MessageResponse(
        message=f"Monitor '{monitor.id}' registered and armed for {monitor.timeout}s",
        monitor=_to_response(monitor),
    )


@router.get("/monitors", response_model=List[MonitorResponse])
def list_monitors():
    return [_to_response(m) for m in store.list()]


@router.get("/monitors/{id}", response_model=MonitorResponse)
def get_monitor(id: str):
    try:
        monitor = store.get(id)
    except MonitorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")
    return _to_response(monitor)


@router.post("/monitors/{id}/heartbeat", response_model=MessageResponse)
def heartbeat(id: str):
    try:
        monitor = store.heartbeat(id)
    except MonitorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")
    return MessageResponse(
        message=f"Heartbeat received. Timer reset to {monitor.timeout}s",
        monitor=_to_response(monitor),
    )


@router.post("/monitors/{id}/pause", response_model=MessageResponse)
def pause(id: str):
    try:
        monitor = store.pause(id)
    except MonitorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")
    return MessageResponse(
        message=f"Monitor '{monitor.id}' paused. No alerts will fire until the next heartbeat",
        monitor=_to_response(monitor),
    )


@router.delete("/monitors/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_monitor(id: str):
    try:
        store.delete(id)
    except MonitorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")
    return None


@router.get("/alerts", response_model=List[AlertRecord])
def list_alerts():
    return store.alerts()
