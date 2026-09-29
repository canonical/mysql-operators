# Hook forensics — reconstructing charm behavior from logs

Reference for `charmed-mysql-log-autopsy` step 4. The Juju hook model has
sharp edges that show up directly in logs. Learn these patterns and most
"weird charm behavior" reads like plain text.

## Failed hooks: retry, backoff, error state

- A hook that exits non-zero is **retried automatically with growing
  backoff** (observed gaps: ~+7s, +13s, +23s, +44s, +88s; roughly 6–10
  attempts), then the unit parks in `error` with
  `hook failed: "<hook-name>"`.
- **Identical traceback on every retry = deterministic bug.**
  **Different error each retry = flake or cascading state change.**
- Uniter marker for the parked state: `awaiting error resolution for
  "<hook>" hook`. Recovery requires `juju resolved <unit>` (re-runs the
  failed hook by default).
- On failure, Juju **rolls back** every relation-databag write and every
  newly created Juju secret made during that hook invocation. This is why
  data-interface diff snapshots get re-armed (see below) and why secret
  `create-time` timestamps in `db-dump.yaml` identify committing attempts.

## Teardown ordering and the `{}` fallback

Relation-broken hooks run serially; each completes (or errors) before the
next starts. Observed scale-down order: `database-peers-relation-broken`
completes first; *after* that, `model.get_relation("database-peers")`
returns `None` in every later hook.

In the charm, `app_peer_data`/`unit_peer_data` are
`ops.RelationDataContent` when `peers` exists but a **plain `{}` fallback**
when `peers is None`. Consequences:

- `del databag[key]` on a real databag **never raises** (ops implements
  deletion as writing `""`; Juju drops empty-string values). On the `{}`
  fallback it is a C-level `dict.__delitem__` and **does** raise `KeyError`.
- `.pop(key, None)` and `.get(key, default)` are safe on both.
- Any handler that can run during app/unit teardown (relation-broken for
  *other* relations, storage-detaching, logging/cos relations) must not
  assume the peer relation exists. The charm's `removing_unit` guard
  (`unit_peer_data.get("unit-status") == "removing"`) covers unit teardown
  but **not** app-level teardown — that gap produced real KeyError bugs.

## Traceback frame analysis

Read the frame stack, not just the exception type:

| Shape | Meaning |
|---|---|
| `KeyError` raised at the charm's line, **no `ops/model.py` frame** beneath | C-level dict op → the object was the `{}` fallback, not the databag. Object type identified from frame shape alone. |
| `KeyError` inside `ops/model.py` frames on databag access | Missing key on a real databag (different fix: guard the key, not the relation) |
| Traceback truncated at the top | The issue's excerpt cut it — pull the full one from the bundle before theorizing |

Also: hook tools' return values are never logged, so frame shape + hook
sequence often substitutes for the missing data.

## Deferred events: lost transitions

ops event lifecycle lines in the charm container log:

- `Deferring <Event>.` — handler postponed it.
- `Re-emitting deferred event <Event>.` — re-emitted from a later hook;
  the surrounding juju-log lines tell you *which hook* re-emitted it.

Failure fingerprints:

- **Deferral with no final re-emission** → the transition never happened;
  whatever state the handler would have set stays stale forever.
- **Handler returns without deferring** on a not-ready branch → same
  effect: the event is dropped silently. Classic result: app status frozen
  at a transitional message ("Setting up replication") while the unit
  moved on to `active` — the app/unit status asymmetry fingerprint.
- Guard predicates that pass "too early" (e.g. peer-data keys present but
  cluster not yet initialized) are the usual reason handlers take the
  wrong branch and drop the event.

## Uniter operation lifecycle (agent busyness)

`juju debug-log` DEBUG lines from `juju.worker.uniter.operation`:

```
... preparing operation "run commands" for <unit>
... executing operation "run commands" for <unit>
... committing operation "run commands" for <unit>
```

Three sources keep a unit's agent in `executing`:

1. Normal hooks (relation events, config-changed, ...).
2. Juju-native `update-status` (default every 5m).
3. **Run-commands operations**: `juju-exec` fired *outside* a hook context.
   The Charmed MySQL charms fork background dispatchers that re-invoke
   their own dispatch — `rotate_mysql_logs` every ~60s and
   `heal_mysql_cluster` every ~120s (greppable as
   `Emitting Juju event rotate_mysql_logs.` / `heal_mysql_cluster.`).
   These share the **one serial uniter queue** with hooks.

Diagnosis for "unit never settles idle / wait-for-idle timeouts":

- Parse durations and gaps with `scripts/parse_uniter_ops.py`.
- Structural failure threshold: **operation duration ≥ the dispatch tick
  period** → queue pile-up, idle gaps collapse to 0–2s, no
  consecutive-idle-samples wait can ever pass.
- Durations depend on the rig: mysqlsh calls take 2–5s locally, 9–72s on
  CI rigs (uniter boot alone can be 11–27s). Never extrapolate local
  timings; compare per-op durations local vs bundle before concluding.

## Status handling mechanics

- `status-set` calls do **not** log their arguments; `AGENT-STATUS` lines
  show only agent state (executing/idle/error), never workload messages.
- Reconstruct transitions from `status-log/*.yaml` + `juju-status` snapshot
  + ordering of log lines around `status-set`-ish events.
- The k8s charm's `_is_cluster_blocked` (despite the name) inspects Group
  Replication member state and async-replication activity, **not** charm
  status. When it returns True, update-status skips entirely — statuses
  seen at timeout are whatever was written in the first minutes. Greppable
  marker: `Skip status update when setting async replication`.
- Unit statuses derived purely from peer-databag `member-state`/`member-role`
  overwrite any status set by other handlers on the next update-status —
  a "blocked" that disappears within one interval was masked, not healed.
