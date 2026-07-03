import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.models import AlertRecord, MonitorStatus


class MonitorNotFoundError(Exception):
    pass


class MonitorAlreadyExistsError(Exception):
    pass


class Monitor:
    """In-memory representation of a single device's dead-man's-switch state."""

    def __init__(self, id: str, timeout: float, alert_email: str):
        self.id = id
        self.timeout = timeout
        self.alert_email = alert_email
        self.status = MonitorStatus.ACTIVE
        self.created_at = datetime.now(timezone.utc)
        self.last_heartbeat_at = self.created_at
        self.deadline: Optional[datetime] = None
        self.timer: Optional[threading.Timer] = None

    def seconds_remaining(self) -> Optional[float]:
        if self.status != MonitorStatus.ACTIVE or self.deadline is None:
            return None
        remaining = (self.deadline - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, remaining)


class MonitorStore:
    """Thread-safe registry of monitors and their countdown timers.

    A threading.Timer fires the alert on its own thread when a device's
    countdown reaches zero, so every mutation is guarded by a single lock
    to avoid races between heartbeats/pauses and an in-flight timeout.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._monitors: Dict[str, Monitor] = {}
        self._alerts: List[AlertRecord] = []

    def create(self, id: str, timeout: float, alert_email: str) -> Monitor:
        with self._lock:
            if id in self._monitors:
                raise MonitorAlreadyExistsError(id)
            monitor = Monitor(id, timeout, alert_email)
            self._monitors[id] = monitor
            self._arm(monitor)
            return monitor

    def get(self, id: str) -> Monitor:
        with self._lock:
            monitor = self._monitors.get(id)
            if monitor is None:
                raise MonitorNotFoundError(id)
            return monitor

    def list(self) -> List[Monitor]:
        with self._lock:
            return list(self._monitors.values())

    def heartbeat(self, id: str) -> Monitor:
        with self._lock:
            monitor = self._monitors.get(id)
            if monitor is None:
                raise MonitorNotFoundError(id)
            self._cancel_timer(monitor)
            monitor.status = MonitorStatus.ACTIVE
            monitor.last_heartbeat_at = datetime.now(timezone.utc)
            self._arm(monitor)
            return monitor

    def pause(self, id: str) -> Monitor:
        with self._lock:
            monitor = self._monitors.get(id)
            if monitor is None:
                raise MonitorNotFoundError(id)
            self._cancel_timer(monitor)
            monitor.status = MonitorStatus.PAUSED
            monitor.deadline = None
            return monitor

    def delete(self, id: str) -> None:
        with self._lock:
            monitor = self._monitors.get(id)
            if monitor is None:
                raise MonitorNotFoundError(id)
            self._cancel_timer(monitor)
            del self._monitors[id]

    def alerts(self) -> List[AlertRecord]:
        with self._lock:
            return list(self._alerts)

    def _arm(self, monitor: Monitor) -> None:
        monitor.deadline = datetime.now(timezone.utc) + timedelta(seconds=monitor.timeout)
        timer = threading.Timer(monitor.timeout, self._on_timeout, args=(monitor.id,))
        timer.daemon = True
        monitor.timer = timer
        timer.start()

    def _cancel_timer(self, monitor: Monitor) -> None:
        if monitor.timer is not None:
            monitor.timer.cancel()
            monitor.timer = None

    def _on_timeout(self, id: str) -> None:
        with self._lock:
            monitor = self._monitors.get(id)
            # Monitor may have been heartbeat/paused/deleted between the
            # timer firing and this callback acquiring the lock.
            if monitor is None or monitor.status != MonitorStatus.ACTIVE:
                return
            monitor.status = MonitorStatus.DOWN
            monitor.deadline = None
            record = AlertRecord(
                monitor_id=monitor.id,
                alert_email=monitor.alert_email,
                message=f"Device {monitor.id} is down!",
                time=datetime.now(timezone.utc),
            )
            self._alerts.append(record)
            fire_alert(record)


def fire_alert(record: AlertRecord) -> None:
    """Simulates sending an alert (email/webhook) for a downed device."""
    print(
        {
            "ALERT": record.message,
            "time": record.time.isoformat(),
            "notify": record.alert_email,
        }
    )


store = MonitorStore()
