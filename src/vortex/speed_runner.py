"""Background speed-test run: up to three models, tested one after another.

Every model ends in the load state it started in: a model the run loaded is
unloaded again; a model already serving is tested and left loaded. A model
that won't fit next to the loaded ones is skipped — nothing else is ever
unloaded to make room. A failure marks that model and the run continues.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from .catalog import Catalog, CatalogEntry
from .lifecycle import READY_TIMEOUT_SECONDS, PortConflictError
from .manager import BusyError, Manager, MemoryConflict
from .operations import OperationStore
from .speedtest import SpeedTestError, measure, save_result

_POLL_SECONDS = 0.1
# Real models take from seconds to minutes to load. The load operation itself
# fails after Vortex's own READY_TIMEOUT_SECONDS, so wait a little longer than
# that: the load, not this runner, decides when a model has failed to come up.
_OP_WAIT_SECONDS = READY_TIMEOUT_SECONDS + 60.0
# Waiting for *other* in-flight operations has a generous ceiling.
_IDLE_WAIT_SECONDS = 900.0


class SpeedRunBusy(Exception):
    """A speed-test run is already in progress."""


def _fit_reason(gb: float | None) -> str:
    return f"won't fit (needs {gb:g} GB)" if gb is not None else "won't fit (size unknown)"


class SpeedRun:
    """Tests 1–3 distinct catalog models in turn on a background thread."""

    def __init__(
        self,
        catalog: Catalog,
        manager: Manager,
        ops: OperationStore,
        results_path: Path,
    ) -> None:
        self._catalog = catalog
        self._manager = manager
        self._ops = ops
        self._results_path = results_path
        self._lock = threading.Lock()
        self._running = False
        self._rows: dict[str, dict[str, str]] = {}

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def rows(self) -> dict[str, dict[str, str]]:
        """Latest run's per-model {"status", "message"}; {} before any run."""
        with self._lock:
            return {mid: dict(row) for mid, row in self._rows.items()}

    def start(self, model_ids: list[str]) -> None:
        """Validate, mark running, and test the models in order on a thread."""
        if not 1 <= len(model_ids) <= 3:
            raise ValueError("pick 1 to 3 models to test")
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("the same model cannot be tested twice in one run")
        for mid in model_ids:
            if self._catalog.by_public_id(mid) is None:
                raise ValueError(f"no catalog entry for {mid!r}")
        with self._lock:
            if self._running:
                raise SpeedRunBusy("a speed test is already running")
            self._running = True
            self._rows = {mid: {"status": "queued", "message": ""} for mid in model_ids}
        threading.Thread(target=self._run, args=(list(model_ids),), daemon=True).start()

    # -- background work -----------------------------------------------------

    def _run(self, model_ids: list[str]) -> None:
        try:
            for mid in model_ids:
                try:
                    self._test_one(mid)
                except Exception as exc:  # noqa: BLE001 — one model's failure must not end the run or strand its status
                    self._set(mid, "failed", f"unexpected error: {exc}")
        finally:
            with self._lock:
                self._running = False

    def _test_one(self, mid: str) -> None:
        entry = self._catalog.by_public_id(mid)
        if entry is None:
            self._set(mid, "failed", f"no catalog entry for {mid!r}")
            return
        if self._is_serving(entry):
            self._finish_serving(entry)
            return
        if not self._manager.admits(entry):
            self._set(mid, "skipped", _fit_reason(entry.ram_estimate_gb))
            return
        self._wait_idle()
        if self._is_serving(entry):
            # A concurrent load finished while we waited — treat as serving.
            self._finish_serving(entry)
            return
        self._set(mid, "loading", "")
        try:
            op_id = self._manager.load(mid)["operation"]
        except MemoryConflict as exc:
            self._set(mid, "skipped", _fit_reason(exc.required_gb))
            return
        except (BusyError, PortConflictError, LookupError) as exc:
            self._set(mid, "failed", str(exc))
            return
        state = self._wait_op(op_id, ("ready", "unloaded", "error"))
        if state == "error":
            self._set(mid, "failed", self._op_message(op_id, "load failed"))
            return
        if state != "ready":
            self._set(mid, "failed", "load timed out")
            # The load is still in flight past the cap. If it later succeeds,
            # the model must be unloaded again — it started unloaded. A
            # background watcher reconciles without holding the run open.
            threading.Thread(
                target=self._reconcile_load, args=(mid, op_id), daemon=True
            ).start()
            return
        self._set(mid, "testing", "")
        error = self._do_test(entry)
        self._set(mid, "unloading", "")
        self._wait_idle()
        try:
            op_id = self._manager.unload(mid)["operation"]
        except (BusyError, PortConflictError, LookupError) as exc:
            self._set(mid, "failed", str(exc))
            return
        state = self._wait_op(op_id, ("unloaded", "error"))
        if state == "unloaded":
            if error is not None:
                self._set(mid, "failed", error)
            else:
                self._set(mid, "done", "unloaded again")
        elif state == "error":
            self._set(mid, "failed", self._op_message(op_id, "unload failed"))
        else:
            self._set(mid, "failed", "unload timed out")

    def _finish_serving(self, entry: CatalogEntry) -> None:
        """Test a model that is already serving; leave it loaded either way."""
        self._set(entry.public_id, "testing", "")
        error = self._do_test(entry)
        if error is not None:
            self._set(entry.public_id, "failed", error)
        else:
            self._set(entry.public_id, "done", "tested, left loaded")

    def _do_test(self, entry: CatalogEntry) -> str | None:
        """Measure and persist; returns the failure reason, or None on success."""
        try:
            result = measure(entry.chat_endpoint, entry.upstream_alias or entry.public_id)
        except SpeedTestError as exc:
            return str(exc)
        save_result(self._results_path, entry.public_id, result)
        return None

    # -- helpers -------------------------------------------------------------

    def _is_serving(self, entry: CatalogEntry) -> bool:
        return self._manager.entry_state(entry, self._ops.active_for(entry.public_id)) == "ready"

    def _set(self, mid: str, status: str, message: str) -> None:
        with self._lock:
            self._rows[mid] = {"status": status, "message": message}

    def _wait_idle(self) -> None:
        """Wait for any in-flight load/unload to finish before mutating."""
        deadline = time.monotonic() + _IDLE_WAIT_SECONDS
        while time.monotonic() < deadline:
            if self._ops.active() is None:
                return
            time.sleep(_POLL_SECONDS)

    def _wait_op(self, op_id: str, terminal: tuple[str, ...],
                 timeout: float | None = None) -> str:
        """Poll an operation until a terminal state; "timeout" if the deadline hits."""
        if timeout is None:
            timeout = _OP_WAIT_SECONDS  # read at call time so tests can shorten it
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            snap = self._ops.snapshot(op_id)
            if snap is not None and snap["state"] in terminal:
                return snap["state"]
            time.sleep(_POLL_SECONDS)
        return "timeout"

    def _reconcile_load(self, mid: str, op_id: str) -> None:
        """Unload a late load success so the model ends where the run found it.

        Runs on its own daemon thread after the run has already marked the
        model failed; it must never block or extend the run itself.
        """
        state = self._wait_op(op_id, ("ready", "unloaded", "error"), _IDLE_WAIT_SECONDS)
        if state != "ready":
            return
        self._wait_idle()
        try:
            op2 = self._manager.unload(mid)["operation"]
        except (BusyError, PortConflictError, LookupError):
            return
        self._wait_op(op2, ("unloaded", "error"), _IDLE_WAIT_SECONDS)

    def _op_message(self, op_id: str, fallback: str) -> str:
        snap = self._ops.snapshot(op_id)
        if snap is not None and snap["message"]:
            return snap["message"]
        return fallback