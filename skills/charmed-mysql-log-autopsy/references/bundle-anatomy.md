# Bundle anatomy — evidence sources and how to read them

Reference for `charmed-mysql-log-autopsy` step 3. Covers the two common
capture formats: **Test Observer log bundles** (charm QA) and
**juju-crashdumps** (`juju crashdump` / controller crashdumps attached to
issues).

## File map

Test Observer bundles (from `relevant_links[].url` of an execution, e.g.
`https://charm.logs.test-observer.canonical.com/production/<exec-id>/index.html`)
contain `junit.xml` and a `juju-controller-*.tar.gz` (juju-crashdump) with:

| Path | Contents | Diagnostic use |
|---|---|---|
| `pod/<unit>.log` | charm container agent log: every hook run, juju-log lines (incl. DEBUG if model logging allows), full Python tracebacks | The primary evidence. Charm behavior lives here. |
| `<unit>-var-log/` | Juju agent (uniter) logs | Hook tooling, retry behavior |
| `debug-log.txt` | `juju debug-log` snapshot: uniter operations, all units interleaved | Operation lifecycle, cross-unit ordering. **Check first/last timestamps — it is a truncated ring buffer.** |
| `status-log/*.yaml` | per-app and per-unit timestamped status transition history (`status`, `message`, `since`) | *When* each status/message was set — impossible from `juju status` snapshots. Does not say *why*. |
| `juju-status.txt` / `.yaml` | final state snapshot | End state; JSON has agent status under `juju-status` (not `agent-status`) |
| `db-dump.yaml` | controller DB dump | Ground truth for relation databags, secrets, permissions (below) |
| `kubernetes-version.txt` | kubectl client/server versions | Environment fingerprinting |

Caveats learned from real cases:

- The bundle's `debug-log.txt` coverage window may end *before* the failing
  event (e.g. timeout) — cross-check with the issue's own excerpts.
- `status-log` capture may start *after* the interesting period (capture
  window ≠ incident window).
- A 403 on `charm.logs.test-observer.canonical.com` means the VPN is off,
  not that the artefact is gone.
- `RunCommands` DEBUG lines (out-of-band `juju-exec` dispatches) appear in
  CI bundles but may be absent from `juju debug-log` on some local rigs;
  `executing` transitions and `Emitting Juju event <name>.` lines are the
  reliable evidence there.

## Grep cookbook

```bash
# Full traceback for an unhandled hook error
grep -n -A30 "Uncaught exception while in charm code" pod/<unit>.log

# Ops version (one line per hook process — also a process-start marker)
grep -n "ops .* up and running" pod/<unit>.log

# Hook sequence and agent state
grep -n "relation-broken\|AGENT-STATUS\|hook failed" debug-log.txt pod/<unit>.log

# Status transitions (charm-side view)
grep -n "status-set\|Set unit status\|Set app status" pod/<unit>.log

# Specific error strings (MySQL error codes appear verbatim)
grep -n "1396\|1045\|gaierror\|Name or service" debug-log.txt

# Event deferral lifecycle
grep -n "Deferring \|Re-emitting deferred event" pod/<unit>.log

# Update-status suppression (status is being frozen by design)
grep -c "Skip status update" pod/<unit>.log

# Scheduled out-of-band dispatches (self-healing / log rotation)
grep -n "Emitting Juju event rotate_mysql_logs\|Emitting Juju event heal_mysql_cluster" debug-log.txt
```

## Correlating lines to hook runs

Every jujuc tool call, juju-log line, and traceback in `pod/<unit>.log` is
suffixed with a **hook-context UUID** (e.g. `... for <unit>-<hook>-<context>`).
Group lines by that UUID to reconstruct one hook invocation end to end.
Juju's automatic retry of a failed hook runs with a **different UUID** —
this is how you separate attempt 1 from attempt 2 in a tangle of lines.

Known blind spot: hook tool outputs (e.g. `relation-ids`, `get_relation`)
are *not* logged — DEBUG shows the jujuc call but never its result. Absence
of an ops frame in a traceback plus the hook sequence is often the only way
to infer what a tool returned (e.g. that `get_relation` returned `None`).

## db-dump.yaml — ground truth for Juju-side state

Parse with python/yaml, not grep — keys like `_id` are compact and the
settings blobs need decoding. What it proves:

- **Relation databags** under `r#<relation-id>#<scope>`: exactly what each
  side had committed at dump time. Use to distinguish "never set" from
  "set then rolled back". Example (from a real case): a provider app
  databag containing only a `data` diff snapshot and `secret-user` — no
  username/endpoints — proved the relation was poisoned and that no future
  `database_requested` custom event could fire.
- **Secret metadata** (`secretMetadata`): `create-time` timestamps each
  hook *commit* (secrets created in a failed hook are rolled back), labels
  like `database.4.user.secret` identify the creating relation, and
  `secretConsumers` shows which remote apps tracked them with which
  permissions. A secret created at the retry's timestamp (not attempt 1's)
  proved which attempt wrote the (wrong) password.

## status-log/*.yaml — status transition timeline

Each entry carries `status`, `message`, `since`. Reconstruct the timeline
for app and unit separately, then correlate with pod-log lines:

- A status set at T and overwritten at T+40s by a `status-set` from
  `update-status` is the fingerprint of the status-masking defect.
- App-status timestamps ≪ unit's last hook run = stale app status from a
  lost/deferred-then-dropped event (the app/unit asymmetry fingerprint).
- Correlate with controller-side K8s admission requests (in controller
  logs) to timestamp object creations (Services, Secrets) when unit logs
  are ambiguous about ordering.

## What is intentionally *not* in bundles

- Workload container stderr beyond what mysqld writes to
  `/var/log/mysql/error.log` (not captured; only charm-container logs are).
- Actual values passed to `status-set` (reconstruct from ordering + status-log).
- Anything outside the model (controller logs only if the dump includes them).
