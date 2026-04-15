"""Lightweight process-local debug event bus.

Producers (historical, providers, routes) call `emit_debug_event(...)`.
The sidecar process registers a sink via `set_debug_event_sink(...)` and
exposes events to the UI through an API endpoint.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

_sink_lock = threading.Lock()
_sink: Callable[[dict[str, Any]], None] | None = None


def set_debug_event_sink(sink: Callable[[dict[str, Any]], None] | None) -> None:
    """Register or clear the active event sink for this process."""
    global _sink
    with _sink_lock:
        _sink = sink


def emit_debug_event(
    category: str,
    action: str,
    message: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Emit a structured debug event to the registered sink (if any)."""
    with _sink_lock:
        sink = _sink
    if sink is None:
        return
    payload: dict[str, Any] = {
        "ts": int(time.time() * 1000),
        "category": str(category),
        "action": str(action),
    }
    if message:
        payload["message"] = str(message)
    if data:
        payload["data"] = data
    try:
        sink(payload)
    except Exception:
        # Debug telemetry must never break business logic.
        return

