# Copyright 2026 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Rolling Ops v1 — coordinated rolling operations for Juju charms.

This library provides a reusable mechanism for coordinating rolling operations
across units of a Juju application using a peer-relation distributed lock.

The library guarantees that at most one unit executes a rolling operation at any
time, while allowing multiple units to enqueue operations and participate
in a coordinated rollout.

## Data model (peer relation)

### Unit databag

Each unit maintains a FIFO queue of operations it wishes to execute.

Keys:
- `operations`: JSON-encoded list of queued `Operation` objects
- `state`: `"idle"` | `"request"` | `"retry-release"` | `"retry-hold"`
- `executed_at`: UTC timestamp string indicating when the current operation last ran

Each `Operation` contains:
- `callback_id`: identifier of the callback to execute
- `kwargs`: JSON-serializable arguments for the callback
- `requested_at`: UTC timestamp when the operation was enqueued
- `max_retry (optional)`: maximum retry count. `None` means unlimited
- `attempt`: current attempt number

### Application databag

The application databag represents the global lock state.

Keys:
- `granted_unit`: unit identifier (unit name), or empty
- `granted_at`: UTC timestamp indicating when the lock was granted

## Operation semantics

- Units enqueue operations instead of overwriting a single pending request.
- Duplicate operations (same `callback_id` and `kwargs`) are ignored if they are
  already the last queued operation.
- When granted the lock, a unit executes exactly one operation (the queue head).
- After execution, the lock is released so that other units may proceed.

## Retry semantics

- If a callback returns `OperationResult.RETRY_RELEASE` the unit will release the
lock and retry the operation later.
- If a callback returns `OperationResult.RETRY_HOLD` the unit will keep the
lock and retry immediately.
- Retry state (`attempt`) is tracked per operation.
- When `max_retry` is exceeded, the failing operation is dropped and the unit
  proceeds to the next queued operation, if any.

## Scheduling semantics

- Only the leader schedules lock grants.
- If a valid lock grant exists, no new unit is scheduled.
- Requests are preferred over retries.
- Among requests, the operation with the oldest `requested_at` timestamp is selected.
- Among retries, the operation with the oldest `executed_at` timestamp is selected.
- Stale grants (e.g., pointing to departed units) are automatically released.

All timestamps are stored in UTC using ISO 8601 format.

## Using the library in a charm

### 1. Declare a peer relation

```yaml
peers:
  restart:
    interface: rolling_op
```

Import this library into src/charm.py, and initialize a RollingOpsManagerV1 in the Charm's
`__init__`. The Charm should also define a callback routine, which will be executed when
a unit holds the distributed lock:

src/charm.py
```python
from charms.rolling_ops.v1.rollingops import RollingOpsManagerV1, OperationResult

class SomeCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)

        self.rolling_ops = RollingOpsManagerV1(
            charm=self,
            relation_name="restart",
            callback_targets={
                "restart": self._restart,
                "failed_restart": self._failed_restart,
                "defer_restart": self._defer_restart,
            },
        )

    def _restart(self, force: bool) -> OperationResult:
        # perform restart logic
        return OperationResult.RELEASE

    def _failed_restart(self) -> OperationResult:
        # perform restart logic
        return OperationResult.RETRY_RELEASE

    def _defer_restart(self) -> OperationResult:
        if not self.some_condition():
            return OperationResult.RETRY_HOLD
        # do restart logic
        return OperationResult.RELEASE
```

Request a rolling operation

```python

    def _on_restart_action(self, event) -> None:
        self.rolling_ops.request_async_lock(
            callback_id="restart",
            kwargs={"force": True},
            max_retry=3,
    )
```

All participating units must enqueue the operation in order to be included
in the rolling execution.

Units that do not enqueue the operation will be skipped, allowing operators
to recover from partial failures by reissuing requests selectively.

Do not include sensitive information in the kwargs of the callback.
These values will be stored in the databag.

Make sure that callback_targets is not dynamic and that the mapping
contains the expected values at the moment of the callback execution.
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from sys import version_info
from typing import Any, Callable, Iterator

from ops import Model, Relation, Unit
from ops.charm import (
    CharmBase,
    RelationChangedEvent,
    RelationDepartedEvent,
)
from ops.framework import EventBase, Object

logger = logging.getLogger(__name__)

# The unique Charmhub library identifier, never change it
LIBID = "20b7777f58fe421e9a223aefc2b4d3a4"

# Increment this major API version when introducing breaking changes
LIBAPI = 1

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 0


def _now_timestamp_str() -> str:
    """UTC timestamp as a string using ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _now_timestamp() -> datetime:
    """UTC timestamp."""
    return datetime.now(timezone.utc)


def _parse_timestamp(timestamp: str) -> datetime | None:
    """Parse timestamp string. Return None on errors to avoid selecting invalid timestamps."""
    try:
        return datetime.fromisoformat(timestamp)
    except Exception:
        return None


class RollingOpsNoRelationError(Exception):
    """Raised if we are trying to process a lock, but do not appear to have a relation yet."""


class RollingOpsDecodingError(Exception):
    """Raised if the content of the databag cannot be processed."""


class RollingOpsInvalidLockRequestError(Exception):
    """Raised if the lock request is invalid."""


@dataclass
class Operation:
    """A single queued operation."""

    callback_id: str
    requested_at: datetime
    max_retry: int | None
    attempt: int
    kwargs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the class attributes."""
        if not isinstance(self.callback_id, str) or not self.callback_id.strip():
            raise ValueError("callback_id must be a non-empty string")

        if not isinstance(self.kwargs, dict):
            raise ValueError("kwargs must be a dict")
        try:
            json.dumps(self.kwargs)
        except TypeError as e:
            raise ValueError(f"kwargs must be JSON-serializable: {e}") from e

        if not isinstance(self.requested_at, datetime):
            raise ValueError("requested_at must be a datetime")

        if self.max_retry is not None:
            if not isinstance(self.max_retry, int):
                raise ValueError("max_retry must be an int")
            if self.max_retry < 0:
                raise ValueError("max_retry must be >= 0")

        if not isinstance(self.attempt, int):
            raise ValueError("attempt must be an int")
        if self.attempt < 0:
            raise ValueError("attempt must be >= 0")

    @classmethod
    def create(
        cls,
        callback_id: str,
        kwargs: dict[str, Any],
        max_retry: int | None = None,
    ) -> "Operation":
        """Create a new operation from a callback id and kwargs."""
        return cls(
            callback_id=callback_id,
            kwargs=kwargs,
            requested_at=_now_timestamp(),
            max_retry=max_retry,
            attempt=0,
        )

    def _to_dict(self) -> dict[str, str]:
        """Dict form (string-only values)."""
        return {
            "callback_id": self.callback_id,
            "kwargs": self._kwargs_to_json(),
            "requested_at": self.requested_at.isoformat(),
            "max_retry": "" if self.max_retry is None else str(self.max_retry),
            "attempt": str(self.attempt),
        }

    def to_string(self) -> str:
        """Serialize to a string suitable for a Juju databag."""
        return json.dumps(self._to_dict(), separators=(",", ":"))

    def increase_attempt(self) -> None:
        """Increment the attempt counter."""
        self.attempt += 1

    def is_max_retry_reached(self) -> bool:
        """Return True if attempt exceeds max_retry (unless max_retry is None)."""
        if self.max_retry is None:
            return False
        return self.attempt > self.max_retry

    @classmethod
    def from_string(cls, data: str) -> "Operation":
        """Deserialize from a Juju databag string.

        Raises:
            RollingOpsDecodingError: if data cannot be deserialized.
        """
        try:
            obj = json.loads(data)

            return cls(
                callback_id=obj["callback_id"],
                requested_at=_parse_timestamp(obj["requested_at"]),
                max_retry=int(obj["max_retry"]) if obj.get("max_retry") else None,
                attempt=int(obj["attempt"]),
                kwargs=json.loads(obj["kwargs"]) if obj.get("kwargs") else {},
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.error("Failed to deserialize Operation from %s: %s", data, e)
            raise RollingOpsDecodingError(f"Failed to deserialize data to create an Operation {e}")

    def _kwargs_to_json(self) -> str:
        """Deterministic JSON serialization for kwargs."""
        return json.dumps(self.kwargs, sort_keys=True, separators=(",", ":"))

    def __eq__(self, other: object) -> bool:
        """Equal for the operation."""
        if not isinstance(other, Operation):
            return False
        return self.callback_id == other.callback_id and self.kwargs == other.kwargs

    def __hash__(self) -> int:
        """Hash for the operation."""
        return hash((self.callback_id, self._kwargs_to_json()))


class OperationQueue:
    """In-memory FIFO queue of Operations with encode/decode helpers for storing in a databag."""

    def __init__(self, operations: list[Operation] | None = None):
        self.operations: list[Operation] = list(operations or [])

    def __len__(self) -> int:
        """Return the number of operations in the queue."""
        return len(self.operations)

    @property
    def empty(self) -> bool:
        """Return True if there are no queued operations."""
        return not self.operations

    def peek(self) -> Operation | None:
        """Return the first operation in the queue if it exists."""
        return self.operations[0] if self.operations else None

    def _peek_last(self) -> Operation | None:
        """Return the last operation in the queue if it exists."""
        return self.operations[-1] if self.operations else None

    def dequeue(self) -> Operation | None:
        """Drop the first operation in the queue if it exists and return it."""
        return self.operations.pop(0) if self.operations else None

    def increase_attempt(self) -> None:
        """Increment the attempt counter for the head operation and persist it."""
        if self.empty:
            return
        self.operations[0].increase_attempt()

    def enqueue_lock_request(
        self, callback_id: str, kwargs: dict[str, Any], max_retry: int | None = None
    ) -> None:
        """Append operation only if it is not equal to the last enqueued operation."""
        operation = Operation.create(callback_id, kwargs, max_retry=max_retry)

        if last_operation := self._peek_last():
            if last_operation == operation:
                return
        self.operations.append(operation)

    def to_string(self) -> str:
        """Encode entire queue to a single string."""
        items = [op.to_string() for op in self.operations]
        return json.dumps(items, separators=(",", ":"))

    @classmethod
    def from_string(cls, data: str) -> "OperationQueue":
        """Decode queue from a string.

        Raises:
            RollingOpsDecodingError: if data cannot be deserialized.
        """
        if not data:
            return cls()

        try:
            items = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to deserialize data to create an OperationQueue from %s: %s", data, e
            )
            raise RollingOpsDecodingError(
                f"Failed to deserialize data to create an OperationQueue from {e}."
            )

        if not isinstance(items, list):
            logger.error("OperationQueue string must decode to a JSON list %s:", data)
            raise RollingOpsDecodingError("OperationQueue string must decode to a JSON list.")

        operations = [Operation.from_string(s) for s in items]
        return cls(operations)


class LockIntent(StrEnum):
    """Unit-level lock intents stored in unit databags."""

    REQUEST = "request"
    RETRY_RELEASE = "retry-release"
    RETRY_HOLD = "retry-hold"
    IDLE = "idle"


class OperationResult(StrEnum):
    """Callback return values."""

    RELEASE = "release"
    RETRY_RELEASE = "retry-release"
    RETRY_HOLD = "retry-hold"


class Lock:
    """State machine view over peer relation databags for a single unit.

    This class is the only component that should directly read/write the peer relation
    databags for lock state, queue state, and grant state.

    Important:
      - All relation databag values are strings.
      - This class updates both unit databags and app databags, which triggers
        relation-changed events.
    """

    def __init__(self, model: Model, relation_name: str, unit: Unit):
        if not model.get_relation(relation_name):
            # TODO: defer caller in this case (probably just fired too soon).
            raise RollingOpsNoRelationError()
        self.relation = model.get_relation(relation_name)
        self.unit = unit
        self.app = model.app

    @property
    def _app_data(self) -> dict:
        return self.relation.data[self.app]

    @property
    def _unit_data(self) -> dict:
        return self.relation.data[self.unit]

    @property
    def _operations(self) -> OperationQueue:
        return OperationQueue.from_string(self._unit_data.get("operations", ""))

    @property
    def _state(self) -> str:
        return self._unit_data.get("state", "")

    def request(
        self, callback_id: str, kwargs: dict[str, Any], max_retry: int | None = None
    ) -> None:
        """Enqueue an operation and mark this unit as requesting the lock.

        Args:
          callback_id: identifies which callback to execute.
          kwargs: dict of callback kwargs.
          max_retry: None -> unlimited retries, else explicit integer.
        """
        queue = self._operations

        previous_length = len(queue)
        queue.enqueue_lock_request(callback_id, kwargs, max_retry)
        if previous_length == len(queue):
            logger.info(
                "Operation %s not added to the queue. It already exists in the back of the queue.",
                callback_id,
            )
            return

        if len(queue) == 1:
            self._unit_data.update({"state": LockIntent.REQUEST})

        self._unit_data.update({"operations": queue.to_string()})
        logger.info("Operation %s added to the queue.", callback_id)

    def _set_retry(self, intent: LockIntent) -> None:
        """Mark the given retry intent on the head operation.

        If max_retry is reached, the head operation is dropped via complete().
        """
        self._increase_attempt()
        if self._is_max_retry_reached():
            logger.warning("Operation max retry reached. Dropping.")
            self.complete()
            return
        self._unit_data.update({
            "executed_at": _now_timestamp_str(),
            "state": intent,
        })

    def retry_release(self) -> None:
        """Indicate that the operation should be retried but the lock should be released."""
        self._set_retry(LockIntent.RETRY_RELEASE)

    def retry_hold(self) -> None:
        """Indicate that the operation should be retried but the lock should be kept."""
        self._set_retry(LockIntent.RETRY_HOLD)

    def complete(self) -> None:
        """Mark the head operation as completed successfully, pop it from the queue.

        Update unit state depending on whether more operations remain.
        """
        queue = self._operations
        queue.dequeue()
        next_state = LockIntent.REQUEST if queue.peek() else LockIntent.IDLE

        self._unit_data.update({
            "state": next_state,
            "operations": queue.to_string(),
            "executed_at": _now_timestamp_str(),
        })

    def release(self) -> None:
        """Clear the application-level grant."""
        self._app_data.update({"granted_unit": "", "granted_at": ""})

    def grant(self) -> None:
        """Grant a lock to a unit."""
        self._app_data.update({
            "granted_unit": str(self.unit.name),
            "granted_at": _now_timestamp_str(),
        })

    def is_granted(self) -> bool:
        """Return True if the unit holds the lock."""
        granted_unit = self._app_data.get("granted_unit", "")
        return granted_unit == str(self.unit.name)

    def should_run(self) -> bool:
        """Return True if the lock has been granted to the unit and it is time to execute callback."""
        return self.is_granted() and not self._unit_executed_after_grant()

    def should_release(self) -> bool:
        """Return True if the unit finished executing the callback and should be released."""
        return self.is_completed() or self._unit_executed_after_grant()

    def is_waiting(self) -> bool:
        """Return True if this unit is waiting for a lock to be granted."""
        return self._state == LockIntent.REQUEST and not self.is_granted()

    def is_completed(self) -> bool:
        """Return True if this unit is completed callback but still has the grant (leader should clear)."""
        return self._state == LockIntent.IDLE and self.is_granted()

    def is_retry(self) -> bool:
        """Return True if this unit requested retry but still has the grant (leader should clear)."""
        unit_intent = self._state
        return (
            unit_intent == LockIntent.RETRY_RELEASE or unit_intent == LockIntent.RETRY_HOLD
        ) and self.is_granted()

    def is_waiting_retry(self) -> bool:
        """Return True if the unit requested retry and is waiting for lock to be granted."""
        return self._state == LockIntent.RETRY_RELEASE and not self.is_granted()

    def is_retry_hold(self) -> bool:
        """Return True if the unit requested retry and wants to keep the lock."""
        return self._state == LockIntent.RETRY_HOLD and not self.is_granted()

    def get_current_operation(self) -> Operation | None:
        """Return the head operation for this unit, if any."""
        return self._operations.peek()

    def _is_max_retry_reached(self) -> bool:
        """Return True if the head operation exceeded its max_retry (unless max_retry is None)."""
        if not (operation := self.get_current_operation()):
            return True
        return operation.is_max_retry_reached()

    def _increase_attempt(self) -> None:
        """Increment the attempt counter for the head operation and persist it."""
        q = self._operations
        q.increase_attempt()
        self._unit_data.update({"operations": q.to_string()})

    def get_last_completed(self) -> datetime | None:
        """Get the time the unit requested a retry of the head operation."""
        if timestamp_str := self._unit_data.get("executed_at", ""):
            return _parse_timestamp(timestamp_str)
        return None

    def get_requested_at(self) -> datetime | None:
        """Get the time the head operation was requested at."""
        if not (operation := self.get_current_operation()):
            return None
        return operation.requested_at

    def _unit_executed_after_grant(self) -> bool:
        """Returns True if the unit executed its callback after the lock was granted."""
        granted_at = _parse_timestamp(self._app_data.get("granted_at", ""))
        executed_at = _parse_timestamp(self._unit_data.get("executed_at", ""))

        if granted_at is None or executed_at is None:
            return False
        return executed_at > granted_at


class LockIterator:
    """Iterator over Lock objects for each unit present on the peer relation."""

    def __init__(self, model: Model, relation_name: str):
        relation = model.relations[relation_name][0]
        units = relation.units
        units.add(model.unit)
        self._model = model
        self._units = units
        self._relation_name = relation_name

    def __iter__(self) -> Iterator[Lock]:
        """Yields a lock for each unit we can find on the relation."""
        for unit in self._units:
            yield Lock(self._model, self._relation_name, unit=unit)


def pick_oldest_completed(locks: list[Lock]) -> Lock | None:
    """Choose the retry lock with the oldest executed_at timestamp."""
    selected = None
    oldest_timestamp = None

    for lock in locks:
        timestamp = lock.get_last_completed()
        if not timestamp:
            continue

        if oldest_timestamp is None or timestamp < oldest_timestamp:
            oldest_timestamp = timestamp
            selected = lock

    return selected


def pick_oldest_request(locks: list[Lock]) -> Lock | None:
    """Choose the lock with the oldest head operation."""
    selected = None
    oldest_request = None

    for lock in locks:
        timestamp = lock.get_requested_at()
        if not timestamp:
            continue

        if oldest_request is None or timestamp < oldest_request:
            oldest_request = timestamp
            selected = lock

    return selected


class RollingOpsLockGrantedEvent(EventBase):
    """Custom event emitted when the background worker grants the lock."""


class RollingOpsManagerV1(Object):
    """Emitters and handlers for rolling ops."""

    def __init__(
        self, charm: CharmBase, relation_name: str, callback_targets: dict[str, Callable]
    ):
        """Register our custom events.

        params:
            charm: the charm we are attaching this to.
            relation_name: the peer relation name from metadata.yaml.
            callback_targets: mapping from callback_id -> callable.
        """
        super().__init__(charm, "rolling-ops-manager")
        self._charm = charm
        self.relation_name = relation_name
        self.callback_targets = callback_targets
        self.charm_dir = charm.charm_dir
        self.worker = RollingOpsAsyncWorker(charm, relation_name=relation_name)

        charm.on.define_event("rollingops_lock_granted", RollingOpsLockGrantedEvent)

        self.framework.observe(
            charm.on[self.relation_name].relation_changed, self._on_relation_changed
        )
        self.framework.observe(
            charm.on[self.relation_name].relation_departed, self._on_relation_departed
        )
        self.framework.observe(charm.on.leader_elected, self._process_locks)
        self.framework.observe(charm.on.rollingops_lock_granted, self._on_rollingops_lock_granted)
        self.framework.observe(charm.on.update_status, self._on_rollingops_lock_granted)

    @property
    def _relation(self) -> Relation | None:
        """Returns the peer relation used to manage locks."""
        return self.model.get_relation(self.relation_name)

    def _on_rollingops_lock_granted(self, event: RollingOpsLockGrantedEvent) -> None:
        """Handler of the custom hook rollingops_lock_granted.

        The custom hook is triggered by a background process.
        """
        if not self._relation:
            return
        logger.info("Received a rolling-ops lock granted event.")
        lock = Lock(self.model, self.relation_name, self.model.unit)
        if lock.should_run():
            self._on_run_with_lock()
            self._process_locks()

    def _on_relation_departed(self, event: RelationDepartedEvent) -> None:
        """Leader cleanup: if a departing unit was granted a lock, clear the grant.

        This prevents deadlocks when the granted unit leaves the relation.
        """
        if not self.model.unit.is_leader():
            return
        if unit := event.departing_unit:
            lock = Lock(self.model, self.relation_name, unit)
            if lock.is_granted():
                lock.release()
                self._process_locks()

    def _on_relation_changed(self, _: RelationChangedEvent) -> None:
        """Process relation changed."""
        if self.model.unit.is_leader():
            self._process_locks()
            return

        lock = Lock(self.model, self.relation_name, self.model.unit)
        if lock.should_run():
            self._on_run_with_lock()

    def _valid_peer_unit_names(self) -> set[str]:
        """Return all unit names currently participating in the peer relation."""
        if not self._relation:
            return set()
        names = {u.name for u in self._relation.units}
        names.add(self.model.unit.name)
        return names

    def _release_stale_grant(self) -> None:
        """Ensure granted_unit refers to a unit currently on the peer relation."""
        if not self._relation:
            return

        if not (granted_unit := self._relation.data[self.model.app].get("granted_unit", "")):
            return

        valid_units = self._valid_peer_unit_names()
        if granted_unit not in valid_units:
            logger.warning(
                "granted_unit=%s is not in current peer units; releasing stale grant.",
                granted_unit,
            )
            self._relation.data[self.model.app].update({"granted_unit": "", "granted_at": ""})

    def _process_locks(self, _: EventBase | None = None) -> None:
        """Process locks.

        This method is only executed by the leader unit.
        It effectively releases the lock and triggers scheduling.
        """
        if not self.model.unit.is_leader():
            return

        for lock in LockIterator(self.model, self.relation_name):
            if lock.should_release():
                lock.release()
                break

        self._release_stale_grant()
        granted_unit = self._relation.data[self.model.app].get("granted_unit", "")

        if granted_unit:
            logger.info("Current granted_unit=%s. No new unit will be scheduled.", granted_unit)
            return

        self._schedule()

    def _schedule(self) -> None:
        """Select and grant the next lock based on priority and queue state.

        This method iterates over all locks associated with the relation and
        determines which unit should receive the lock next.

        Priority order:
        1. Units in RETRY_HOLD state are immediately granted the lock.
        2. Units in REQUEST state are considered next (oldest request first).
        3. Units in RETRY_RELEASE state are considered last (oldest completed first).

        If no eligible lock is found, no action is taken.

        Once a lock is selected, it is granted via `_grant_lock`.
        """
        logger.info("Starting scheduling.")

        pending_requests = []
        pending_retries = []

        for lock in LockIterator(self.model, self.relation_name):
            if lock.is_retry_hold():
                self._grant_lock(lock)
                return
            if lock.is_waiting():
                pending_requests.append(lock)
            elif lock.is_waiting_retry():
                pending_retries.append(lock)

        selected = None
        if pending_requests:
            selected = pick_oldest_request(pending_requests)
        elif pending_retries:
            selected = pick_oldest_completed(pending_retries)

        if not selected:
            logger.info("No pending lock requests. Lock was not granted to any unit.")
            return

        self._grant_lock(selected)

    def _grant_lock(self, selected: Lock) -> None:
        """Grant the lock to the selected unit.

        If the lock is granted to the leader unit:
            - If it is a retry, starts the worker to break the loop before next execution.
            - Otherwise, the callback is run immediately

        Args:
            selected: The lock instance to grant.
        """
        selected.grant()
        logger.info("Lock granted to unit=%s.", selected.unit.name)
        if selected.unit == self.model.unit:
            if selected.is_retry():
                self.worker.start()
                return
            self._on_run_with_lock()
            self._process_locks()

    def request_async_lock(
        self,
        callback_id: str,
        kwargs: dict[str, Any] | None = None,
        max_retry: int | None = None,
    ) -> None:
        """Enqueue a rolling operation and request the distributed lock.

        This method appends an operation (identified by callback_id and kwargs) to the
        calling unit's FIFO queue stored in the peer relation databag and marks the unit as
        requesting the lock. It does not execute the operation directly.

        Args:
            callback_id: Identifier for the callback to execute when this unit is granted
                the lock. Must be a non-empty string and must exist in the manager's
                callback registry.
            kwargs: Keyword arguments to pass to the callback when executed. If omitted,
                an empty dict is used. Must be JSON-serializable because it is stored
                in Juju relation databags.
            max_retry: Retry limit for this operation. None means unlimited retries.
                0 means no retries (drop immediately on first failure). Must be >= 0
                when provided.

        Raises:
            RollingOpsInvalidLockRequestError: If any input is invalid (e.g. unknown callback_id,
                non-dict kwargs, non-serializable kwargs, negative max_retry).
            RollingOpsNoRelationError: If the peer relation does not exist.
        """
        if callback_id not in self.callback_targets:
            raise RollingOpsInvalidLockRequestError(f"Unknown callback_id: {callback_id}")

        try:
            if kwargs is None:
                kwargs = {}
            lock = Lock(self.model, self.relation_name, self.model.unit)
            lock.request(callback_id, kwargs, max_retry)

        except (RollingOpsDecodingError, ValueError) as e:
            logger.error("Failed operation: %s", e)
            raise RollingOpsInvalidLockRequestError(f"Failed to create the lock request: {e}")
        except RollingOpsNoRelationError as e:
            logger.debug("No %s peer relation yet.", self.relation_name)
            raise e

        if self.model.unit.is_leader():
            self._process_locks()

    def _on_run_with_lock(self) -> None:
        """Execute the current head operation if this unit holds the distributed lock.

        - If this unit does not currently hold the lock grant, no operation is run.
        - If this unit holds the grant but has no queued operation, lock is released.
        - Otherwise, the operation's callback is looked up by `callback_id` and
            invoked with the operation kwargs.
        """
        lock = Lock(self.model, self.relation_name, self.model.unit)

        if not lock.is_granted():
            logger.debug("Lock is not granted. Operation will not run.")
            return

        if not (operation := lock.get_current_operation()):
            logger.debug("There is no operation to run.")
            lock.complete()
            return

        if not (callback := self.callback_targets.get(operation.callback_id, "")):
            logger.warning(
                "Operation %s target was not found. It cannot be executed.",
                operation.callback_id,
            )
            return
        logger.info(
            "Executing callback_id=%s, attempt=%s", operation.callback_id, operation.attempt
        )
        try:
            result = callback(**operation.kwargs)
        except Exception as e:
            logger.exception("Operation failed: %s: %s", operation.callback_id, e)
            result = OperationResult.RETRY_RELEASE

        match result:
            case OperationResult.RETRY_HOLD:
                logger.info(
                    "Finished %s. Operation will be retried immediately.", operation.callback_id
                )
                lock.retry_hold()

            case OperationResult.RETRY_RELEASE:
                logger.info("Finished %s. Operation will be retried later.", operation.callback_id)
                lock.retry_release()

            case _:
                logger.info("Finished %s. Lock will be released.", operation.callback_id)
                lock.complete()


class RollingOpsAsyncWorker(Object):
    """Spawns and manages the external rolling-ops worker process."""

    def __init__(self, charm: CharmBase, relation_name: str):
        super().__init__(charm, "rollingops-async-worker")
        self._charm = charm
        self._peers_name = relation_name
        self._run_cmd = "/usr/bin/juju-exec"

    @property
    def _relation(self) -> Relation:
        """Returns the peer relation."""
        return self._charm.model.get_relation(self._peers_name)

    @property
    def _app_data(self) -> dict:
        """Returns the application databag in the peer relation."""
        return self._relation.data[self.model.app]

    def start(self) -> None:
        """Start a new worker process."""
        if self._relation is None:
            return
        self.stop()

        # Remove JUJU_CONTEXT_ID so juju-run works from the spawned process
        new_env = os.environ.copy()
        new_env.pop("JUJU_CONTEXT_ID", None)

        for loc in new_env.get("PYTHONPATH", "").split(":"):
            path = Path(loc)
            venv_path = (
                path
                / ".."
                / "venv"
                / "lib"
                / f"python{version_info.major}.{version_info.minor}"
                / "site-packages"
            )
            if path.stem == "lib":
                new_env["PYTHONPATH"] = f"{venv_path.resolve()}:{new_env['PYTHONPATH']}"
                break

        worker = self._charm.charm_dir / "lib/charms/rolling_ops/v1" / "rollingops.py"

        pid = subprocess.Popen(
            [
                "/usr/bin/python3",
                "-u",
                str(worker),
                "--run-cmd",
                self._run_cmd,
                "--unit-name",
                self._charm.model.unit.name,
                "--charm-dir",
                str(self._charm.charm_dir),
            ],
            cwd=str(self._charm.charm_dir),
            stdout=open("/var/log/rollingops_worker.log", "a"),
            stderr=subprocess.STDOUT,
            env=new_env,
        ).pid

        self._app_data.update({"rollingops-worker-pid": str(pid)})
        logger.info("Started RollingOps worker process with PID %s", pid)

    def stop(self) -> None:
        """Stop the running worker process if it exists."""
        if self._relation is None:
            return

        if not (pid_str := self._app_data.get("rollingops-worker-pid", "")):
            return

        pid = int(pid_str)
        try:
            os.kill(pid, signal.SIGINT)
            logger.info("Stopped RollingOps worker process PID %s", pid)
        except OSError:
            logger.info("Failed to stop RollingOps worker process PID %s", pid)

        self._app_data.update({"rollingops-worker-pid": ""})


def main():
    """Juju hook event dispatcher."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-cmd", required=True)
    parser.add_argument("--unit-name", required=True)
    parser.add_argument("--charm-dir", required=True)
    args = parser.parse_args()

    # Sleep so that the leader unit can properly leave the hook and start a new one
    time.sleep(10)
    dispatch_sub_cmd = (
        f"JUJU_DISPATCH_PATH=hooks/rollingops_lock_granted {args.charm_dir}/dispatch"
    )
    res = subprocess.run([args.run_cmd, "-u", args.unit_name, dispatch_sub_cmd])
    res.check_returncode()


if __name__ == "__main__":
    main()
