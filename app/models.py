from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class MonitorStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DOWN = "down"


class MonitorCreateRequest(BaseModel):
    id: str = Field(..., min_length=1, description="Unique device identifier")
    timeout: float = Field(..., gt=0, description="Seconds allowed between heartbeats")
    alert_email: EmailStr = Field(..., description="Email to notify on failure")


class MonitorResponse(BaseModel):
    id: str
    status: MonitorStatus
    timeout: float
    alert_email: EmailStr
    created_at: datetime
    last_heartbeat_at: datetime
    seconds_remaining: Optional[float] = None


class MessageResponse(BaseModel):
    message: str
    monitor: MonitorResponse


class AlertRecord(BaseModel):
    monitor_id: str
    alert_email: EmailStr
    message: str
    time: datetime
