# Failure taxonomy — signature → likely cause → confirmation

Quick-reference tables distilled from real Charmed MySQL debugging cases.
Use in `charmed-mysql-log-autopsy` step 7 (and as a triage shortcut in
`charmed-mysql-nightly-triage`). Read the row, confirm with the listed
evidence, then apply the corresponding forensics reference.

## Hook failures and crashes

| Signature | Likely cause | Confirm with |
|---|---|---|
| Unit `error: hook failed: "<hook>"`, same traceback on ~6–10 retries with growing gaps, then parked | Unhandled hook exception (deterministic bug) | Traceback in `pod/<unit>.log`; retry timestamps |
| `KeyError` at charm line, **no ops frame** beneath, shortly after `*-peers-relation-broken` | Peer relation gone → `peers is None` → `{}` fallback; teardown ordering | Frame shape; hook timestamps in unit log |
| `KeyError` on `del databag[key]` during scale-down / relation teardown | Same `{}` fallback (`del` is safe on real databags, unsafe on the fallback) | Traceback frames; which relation broke first |
| `code 1396 Operation CREATE USER failed` on a hook *retry* | Non-idempotent user creation after a partially-successful first attempt (MySQL state survives Juju rollback) | Prior attempt's `CREATE USER` success; diff-snapshot state in `db-dump.yaml` |
| Provider active/healthy, requirer waiting "Incorrect/incomplete data" forever | Relation setup poisoned after a partial first attempt; retry path disarmed (clean-exit handler committed the diff snapshot) | Provider app databag in db-dump (no credentials); one hook failure + a *clean* retry earlier in the log |
| Secret exists but credentials never published | Password cached in databag; hook failed before `set_credentials`; retry regenerated it | `secretMetadata.create-time` vs first-attempt timestamps |

## Status anomalies

| Signature | Likely cause | Confirm with |
|---|---|---|
| Blocked status visible, then `active` again within ~1 update-status interval | update-status overwrite (status derived purely from `member-state`/`member-role`) | `status-set` ordering vs "Unit workload member-state is ONLINE" log line; `status-log/*.yaml` |
| App in transitional status (e.g. maintenance "Setting up replication") + unit active, frozen for the whole wait | Lost event transition: deferral never re-emitted, or handler returned without deferring | Count `Deferring` vs `Re-emitting deferred event`; app-status timestamp ≪ unit's last hook |
| Deploy wait timeout; offer side blocked "Ready to create replication"; consumer app maintenance | **Action-gated interface** — reaching active requires an operator action (e.g. `create-replication`) that the harness never runs | Grep the action name in the CI log (0 hits); CIT spec has no actions concept |
| `Skip status update when setting async replication` repeated; statuses never change | update-status suppression by design (`_is_cluster_blocked` + async `idle=False`) | Grep count; check `replication-ready`/`secret-id` in relation data |
| Unit active "Primary" but application is a replica in a cluster-set | "Primary" means *local GR primary*, not cluster-set primary — do not infer async roles from unit statuses | Relation databag (`replication-ready`, `secret-id`, `replica-state`); `get-cluster-status` payload |

## Cluster health

| Signature | Likely cause | Confirm with |
|---|---|---|
| `get-cluster-status` action fails: "Failed to read cluster status" | NO_QUORUM from that unit's perspective (`cluster.status()` requires quorum) — the failure *is* the signal | Unit's member count vs live members; GR logs |
| Members stuck OFFLINE/UNKNOWN + "auto-rejoin attempts are exhausted" + "Cannot perform manual rejoin" | Majority loss deadlock (designed): no quorum → no expulsion → no view shrink | GR membership view; which members are reachable |
| mysqlsh refusal "Cannot perform operation on an healthy cluster..." on `promote-to-primary force=true` | **By design**: force-quorum only valid on a cluster *without* quorum | `get-cluster-status` at action time (`OK*` = refusal correct) |
| One unit ONLINE, others UNREACHABLE, status NO_QUORUM persisting | Quorum lost and members truly down; only exits: members returning reachable, or force-quorum | `replication_group_members`; pebble/mysqld state on other units |
| Degraded status (`OK_NO_TOLERANCE*`) but actions/queries succeed | Partial failure, cluster still quorate — usually *not* the bug being reported | Topology from `get-cluster-status` |

## CI / harness

| Signature | Likely cause | Confirm with |
|---|---|---|
| CI job red with **no pytest output**, failure during setup (concierge/snap/microk8s) | Runner infra flake, unrelated to the change | CI log tail before pytest would start |
| `JujuWaitTimeoutError`, workload active/healthy, unit agent oscillating idle→executing every 1–3 min, never error | Charm schedules out-of-band dispatches (rotate/heal) saturating the uniter queue | `Emitting Juju event` cadence; `scripts/parse_uniter_ops.py` (gaps → 0–2s, long continuous stretches) |
| Same test passes in repo CI, fails in charm-integration-testing | Different wait budgets (repo jubilant: 3 consecutive samples; CIT: 10 consecutive + agents idle) | Which harness produced the failure; agent-status sampling |
| GitHub job `conclusion: success` but test failed | CIT reports failures only via Test Observer; pytest exit 1 doesn't fail the job | Test Observer result for the execution |
| Wait timeout with apps list ≠ units list in the error (e.g. `applications: ['a','b'], units: ['b/0']`) | App/unit status mismatch: one app failed at app level while its units are active | status-log yaml: app message timestamp vs unit's last hook |
| `RuntimeError: Failed to resolve canonical name for <svc>` in relation setup | Unretried DNS resolution right after K8s Service creation (propagation race or deleted Service) | Traceback frame; Service admission timestamps vs hook time |
| Deployment works locally, times out on CI only on arm64 (or only slow rigs) | Timing-sensitive thresholds (30s readiness waits vs 41s+ slow-hardware startup) | Per-op/startup durations local vs bundle |

## Persistence / environment

| Signature | Likely cause | Confirm with |
|---|---|---|
| Snap service crash-looping after a snap refresh, `SnapError: ... Start request repeated too quickly` | systemd `StartLimitBurst` (5 crashes/10s) from a crash on startup; config baked with old `$SNAP_DATA` revision paths | `journalctl -u snap.charmed-mysql.*-service` ("Start request repeated too quickly", "Permission denied" writing old revision dir) |
| `Access denied` for a user whose recipe worked before | Passwords rotate on every charm refresh/redeploy | Re-fetch via `get-password`; deployment freshness |
| Charm behavior differs from current git source | Deployed revision ≠ checkout (branch divergence, renamed databag keys, fetched libs) | `git show origin/<branch>:<path>` for the deployed rev; `unzip -p <charm> <file>` |
