#utils/telemetry.py

import json, time, uuid, threading
from collections import deque
from typing import Any, Dict, Iterable, List, Optional

# ---- in-memory ring buffer (process-local) ----
_MAX_EVENTS = 5000
_EVENTS = deque(maxlen=_MAX_EVENTS)
_LOCK = threading.Lock()

def _now_ms() -> int:
    return int(time.time() * 1000)

def _emit(kind: str, name: str, data: Dict[str, Any], level: str = "info"):
    payload = {"ts_ms": _now_ms(), "trace_id": data.get("trace_id"), "kind": kind, "name": name, "level": level, **data}
    with _LOCK:
        _EVENTS.append(payload)
    # console line (kept for debugging)
    print(json.dumps(payload, default=str, ensure_ascii=False))

def log_event(kind: str, name: str, data: Dict[str, Any] | None = None, level: str = "info"):
    _emit(kind, name, data or {}, level)

class perf_timer:
    def __init__(self, kind: str, name: str, data: Dict[str, Any] | None = None, level: str = "info"):
        self.kind, self.name, self.data, self.level = kind, name, data or {}, level
    def __enter__(self):
        self.t0 = time.perf_counter()
        log_event(self.kind, f"{self.name}:start", {**self.data})
        return self
    def __exit__(self, exc_type, exc, tb):
        dt = int((time.perf_counter() - self.t0) * 1000)
        extra = {"latency_ms": dt}
        if exc is not None:
            extra["error"] = repr(exc)
            _lvl = "error"
        else:
            _lvl = self.level
        log_event(self.kind, f"{self.name}:end", {**self.data, **extra}, level=_lvl)

# ---- API expected by telemetry.dashboard ----
def recent_events(
    limit: int = 100,
    kinds: Optional[Iterable[str]] = None,
    names: Optional[Iterable[str]] = None,
    since_ts_ms: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return recent events (most recent first). Filters are optional."""
    with _LOCK:
        items = list(_EVENTS)  # snapshot
    if kinds:
        kset = set(kinds); items = [e for e in items if e.get("kind") in kset]
    if names:
        nset = set(names); items = [e for e in items if e.get("name") in nset]
    if since_ts_ms:
        items = [e for e in items if (e.get("ts_ms") or 0) >= since_ts_ms]
    return list(reversed(items[-limit:]))

def clear_events():
    with _LOCK:
        _EVENTS.clear()

def stage_start(trace_id: str, stage: str, meta: dict | None = None):
    log_event("STAGE", f"{stage}:start", {"trace_id": trace_id, **(meta or {})})

def stage_end(trace_id: str, stage: str, ok: bool = True, error: str | None = None, meta: dict | None = None):
    payload = {"trace_id": trace_id, "ok": ok, **(meta or {})}
    if error: payload["error"] = error
    log_event("STAGE", f"{stage}:end", payload, level="error" if not ok else "info")

class stage_timer:
    def __init__(self, trace_id: str, stage: str, meta: dict | None = None):
        self.trace_id, self.stage, self.meta = trace_id, stage, meta or {}
    def __enter__(self):
        stage_start(self.trace_id, self.stage, self.meta); return self
    def __exit__(self, exc_type, exc, tb):
        # FIX: Pass self.meta to stage_end so metadata is included in end event
        stage_end(self.trace_id, self.stage, ok=exc is None, error=repr(exc) if exc else None, meta=self.meta)