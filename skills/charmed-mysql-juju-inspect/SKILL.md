---
name: charmed-mysql-juju-inspect
description: >
  Inspects a live Charmed MySQL deployment through Juju,
  gets MySQL cluster status, gets MySQL credentials,
  executes MySQL queries, pulls MySQL logs, and diagnoses
  MySQL failures from logs, crashdumps and tracebacks to
  a root cause.
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.6.0"
  upstream-repo: canonical/mysql-operators
---

# Charmed MySQL Juju inspection

## Overview

A read-only interrogation sequence for live Charmed MySQL deployments
(both the VM `mysql` charm and the K8s `mysql-k8s` charm). The core
insight it encodes: **`juju status` is the charm's opinion, lagging by up
to the update-status interval (default 5m)** — real cluster truth comes
from actions, MySQL itself, and the logs. Also covers the physical
topology (containers, ports, pebble) that everything else depends on.

When the deployment is **not reachable** — a Test Observer bundle, a
crashdump, pasted logs — work offline from captured artifacts only:
every claim must be derivable from the artifacts plus source code,
never from the live system. The steps below cover both modes; the
offline-specific parts are marked as such. Charm errors and statuses
are raised from a small, greppable surface either way: grep the exact
message string in the repo to find the emitting class, the tests
asserting it, and `docs/reference/charm-statuses.md`.

Generic Juju CLI mechanics — flag order, `juju ssh` vs `juju exec`,
actions vs shell commands, status JSON parsing conventions, pebble CLI,
model/controller selection — live in the **`juju-cli` skill**. Load it
whenever a juju command misbehaves; this skill only covers the
Charmed-MYSQL-specific interpretation and the exact commands shown here.

Core topology facts (details in references):

- K8s pods have **two containers**: `charm` and `mysql`. `juju ssh <unit>`
  lands in the charm container; `juju ssh --container mysql <unit>` in the
  workload. mysqlsh/mysqld/pebble live only in the workload container.
- The charm's control channel uses the **MySQL admin interface on port
  33062** (user `serverconfig`), *not* the client port 3306. The admin
  interface ignores `max_connections` and `admin_address` is read-only at
  runtime. mysqlsh's `cluster.status()` probes *members* on port 3306.
- Credentials rotate on every charm refresh/redeploy.

## Interrogation sequence

Run in order; each step either clears a hypothesis or sharpens it. Load
reference files when a step needs depth.

### 1. Assess status

```bash
juju status -m <model> --format json
```

Generic status reading — the three-column model (app status vs unit
workload-status vs unit agent-status), the JSON keying
(`applications.<app>.units.<unit>.juju-status.current`, **not**
`agent-status`), agent-state semantics (`executing` = scheduled
out-of-band dispatches, not a hung workload), the free-text `message`,
and the update-status lag — is in the `juju-cli` skill ("Reading juju
status"). Only the Charmed-MySQL interpretation is repeated here:

- Find **Charm revisions** per app from `juju status`, and the
  **channel/branch** they imply (8.0/stable, 8.4/edge, ...).
- Find **Juju version, Kubernetes client/server versions, MySQL version**:
  the `get-cluster-status` payload embeds the member MySQL `version`;
  k8s versions are in `kubernetes-version.txt` (captures); ops version
  appears in logs as `ops <X> up and running.` — one line per hook
  process.
- Derive topology. Determine **whether a router is in the path** — many
  "database" symptoms are router symptoms and vice versa: look for a
  `mysql-router` app related via `backend-database` (in `juju status`
  output, or the captured `juju-status.yaml`/`db-dump.yaml`), for
  `mysqlrouter`/`charmed_router` log mentions, and remember router
  chains (router below router) are known-buggy territory.
- Read the code **of the branch/revision that was deployed**, not your
  checkout: `git show origin/8.0/edge:<path>` / `git show <charm>/revNNN:<path>`.
  Revision↔tag mapping is in the `mysql-operators-source` skill.
- **8.0 vs 8.4 divergence**: the same lib file ships on both branches with
  diverging refactors and renamed databag keys. Grep the branch that
  matches the deployed revision. The `kubernetes/` and `machines/` copies
  of shared libs are kept byte-identical — a fix must usually touch both.
- **Consecutive Charmhub revision numbers are often arch/channel pairs**,
  not feature revisions (e.g. 747=arm64, 748=amd64 of the same code).
- **Read app status AND unit status separately.** They are set by
  different code paths. App `blocked` with unit `active` (e.g. app-level
  relation blocks) and app `maintenance` + unit `active "Primary"` are
  both real and mean different things than either alone. App status is
  rebuilt only by the leader in specific handlers — app `maintenance` +
  unit `active` is typically a *stale app status from a lost event*, not
  a second broken unit.
- The unit message "Primary" means *local Group Replication primary*,
  not cluster-set primary.
- Statuses are the charm's *opinion*: derived on update-status, lagging
  reality by up to the update-status interval, and masking each other
  (blocked overwritten within one interval). A blocked status that
  "healed itself" after ~40s–5min was masked, not fixed. Never time
  anything against `juju status` — poll actions (step 2) instead.
- **`update-status-hook-interval`** is a legitimate observation dial (e.g.
  `juju model-config update-status-hook-interval=15s` to see masking
  happen, or 30m to freeze reactions during experiments) — remember to
  restore it.
- A unit parked in **`unknown`** right after deploy means its hooks never
  completed. On K8s the classic cause is a deploy without `--trust` (the
  RBAC race — the charm service account can't read `nodes` at cluster
  scope); the log signature and fix are in the `juju-cli` skill's Deploy
  section.

For offline debugging / autopsy, know what each file can and cannot prove.
Full file map, grep cookbook, and `db-dump.yaml` parsing:
[bundle-anatomy.md](references/bundle-anatomy.md).

| Evidence | Proves | Cannot prove |
|---|---|---|
| `pod/<unit>.log` | charm hook execution, juju-log lines, full tracebacks | workload-side (mysqld) internals |
| `debug-log.txt` | uniter operations, hook lifecycle, controller view | (often truncated — check window) |
| `status-log/*.yaml` | exact status/message transition timestamps | *why* a status was set |
| `db-dump.yaml` | relation databags, secret metadata, permissions | charm-side timing |
| `juju-status.txt` | final state snapshot | history |
| workload `error.log` | mysqld/GR server-side truth | charm behavior |

For live deployments, you can verify what is deployed as follows:
juju ssh -m <model> mysql-k8s/0 \
  "grep -n '<marker string>' /var/lib/juju/agents/unit-mysql-k8s-0/charm/src/charm.py"
```

- Deployed source lives at `/var/lib/juju/agents/unit-<app>-<n>/charm/`
  (`src/`, `lib/`, `venv/`). A local `.charm` file can be months stale —
  check mtime and `unzip -p <charm-file> <path> | grep <marker>` before
  deploying it for verification.
- Behavior that "should exist" in current git but doesn't appear in logs
  is often just an older deployed revision. For revision↔tag mapping and
  reading source at a deployed revision, see the `mysql-operators-source`
  skill.

### 2. Get cluster status from actions

```bash
juju run -m <model> mysql-k8s/0 get-cluster-status           # cluster view
juju run -m <model> mysql-k8s/0 get-cluster-status cluster-set=true
```

Interpretation (payload is mysqlsh's cluster status, JSON):

- `defaultreplicaSet.status`: `ok` (quorate, full members), `ok_no_tolerance`
  / `ok_no_tolerance_partial` (quorate but zero fault tolerance),
  `no_quorum`, `offline`. `topology` maps member →
  `status`/`memberrole`/`mode`.
- **A failing read is a signal**: the action failing with
  "Failed to read cluster status" means `cluster.status()` could not
  establish quorum *from that unit* — i.e. NO_QUORUM from its perspective.
  Do not treat it as a setup error.
- The action succeeds on any reachable member (the charm roams to
  `self.instance_address`, which moves after failovers) — success does not
  mean every member is reachable; check per-member entries and
  `shellconnecterror` strings (member probes on 3306 failing).
- Other useful read-only actions: `get-password username=root|serverconfig|clusteradmin`,
  `list-backups` (needs S3 relation).

### 3. Map containers, services, and ports

```bash
# Workload container: services ground truth
juju ssh -m <model> --container mysql mysql-k8s/0 "/charm/bin/pebble services"
juju ssh -m <model> --container mysql mysql-k8s/0 "/charm/bin/pebble plan"
```

Pebble CLI mechanics (`services`/`plan`/`stop|start`, startup config vs
runtime state, `backoff` semantics) are in the `juju-cli` skill ("Pebble:
services and the plan"). What is MySQL-specific here:

- Expected services: `mysqld` (enabled/active — the daemon), `mysql`
  (log tail helper), `mysqld_exporter` (disabled unless COS-related),
  `mysql-pitr-helper-collector` (disabled unless PITR/binlogs
  configured). `mysqld` runs *directly* (`--datadir=/var/lib/mysql`)
  with `kill-delay: 24h` (SIGTERM → graceful shutdown takes a long
  time) — visible in the `pebble plan` output.

Port map (load [k8s-topology.md](references/k8s-topology.md) for the full
picture): 3306 classic protocol + member probes; 33060 X protocol;
**33062 admin interface** (charm control channel). A service can be
Running while its mysqld is dead — check pebble + a SQL probe, not pod state.

**Router presence check**: if a `mysql-router` charm app is related to the
database (via `backend-database`), client connectivity issues may be router
issues — check the router app/unit statuses and its logs before blaming
mysqld. Router chaining (router below router) is legal but
known-problematic territory.

### 4. Reconstruct the failure (from evidence)

Load [hook-forensics.md](references/hook-forensics.md) for the full
pattern catalog. Highlights:

- Issue reports and AI-generated triages are **leads, not facts** —
  verify every causal claim cheaply (revision A/B, git archaeology)
  before building on it; premises like "this is a regression in rev X"
  or "the hook never ran" have repeatedly been refuted.
- Group log lines by **hook-context UUID** to reconstruct single hook
  invocations; a Juju retry of a failed hook carries a different UUID.
- Read tracebacks by **frame shape**: which lines belong to the charm vs
  `ops/model.py` vs site-packages. A `KeyError` at a charm line with *no
  ops frame* underneath means a plain-dict operation — frequently the
  `{}` fallback returned when the peer relation no longer exists.
- Teardown ordering: once `database-peers-relation-broken` completes,
  every later hook sees `peers = None`.
- Count `Deferring ...` vs `Re-emitting deferred event ...` lines; a
  deferral with no final re-emission — or a handler that returned without
  deferring — means a lost state transition (classic cause of stale app
  statuses).
- If the failure is about agent busyness/idle timeouts, parse the uniter
  operation lifecycle with `scripts/parse_uniter_ops.py`.
- Distinguish expected noise from symptoms (e.g. a charm related to
  `data-integrator` blocks until configured — by design; see
  [failure-taxonomy.md](references/failure-taxonomy.md)).
- Anchor deployed tracebacks by **line content, not number** — line
  numbers drift between the deployed revision and current branches.
- If a log line has no hit in the charm repo, search dependency code under
  the charm's venv/site-packages (e.g. `mysql_shell` library ERROR strings).

### 5. Credentials

```bash
juju run -m <model> mysql-k8s/0 get-password username=serverconfig
```

- `root` — full SQL; `serverconfig` — the charm's control user
  (**admin-port 33062 access**); `clusteradmin` — cluster admin, **lacks
  `SERVICE_CONNECTION_ADMIN`** so it *cannot* log in on 33062.
- All secret values also visible via `juju show-secret --reveal` (peer
  secret label `database-peers.mysql-k8s.app`).
- **Re-fetch after every refresh/redeploy** — passwords rotate. `Access
  denied` on a known-good recipe means "check deployment freshness" first.

### 6. MySQL logs

Workload-side (mysqld, audit):

```bash
juju ssh -m <model> --container mysql mysql-k8s/0 \
  "tail -50 /var/log/mysql/error.log; ls /var/log/mysql/archive_error/"
# error.log may be empty between rotations; recent history is in archive_error/*.gz (zcat)
```

- Scheduled dispatches appear as `Emitting Juju event rotate_mysql_logs.`
  (per minute) and `heal_mysql_cluster.` (every ~2m) — normal, not errors.
- Charm-side (hooks, events, tracebacks): `juju debug-log` — see the
  `juju-cli` skill ("Logs, logging levels, logging config").

### 7. Direct SQL and mysqlsh

Quick SQL probe via the mysql client (credentials from step 5; on K8s
run inside the workload container):

```bash
PW=$(...)  # from get-password
juju ssh -m <model> --container mysql mysql-k8s/0 \
  "mysql -u root -p$PW -e 'select member_id, member_state, member_role from performance_schema.replication_group_members'"
```

Useful probes: `replication_group_members` (live GR view),
`SELECT @@super_read_only, @@group_replication_single_primary_mode;`,
`SHOW GRANTS FOR '<user>'@'%';`, `SELECT CURRENT_ROLE();` (returns `NONE`
over X Protocol when roles aren't auto-activated — see
[charm-users.md](references/charm-users.md)).

#### mysqlsh (MySQL Shell) — modes, connections, admin API

mysqlsh is the only client that speaks the admin API
(`dba.getCluster()`, `cluster.status()`) — the `get-cluster-status` action
is just the charm wrapping it. Useful when you need the API directly,
different privileges, or richer output than the action returns.

**Three interactive modes, two wire protocols.** JavaScript is the
default mode of a bare `mysqlsh` session; Python and SQL are opt-in.
Switch interactively with `\sql`, `\js`, `\py`.

| Start with | Session mode | Protocol |
|---|---|---|
| `mysqlsh` | JavaScript | auto-detect (prefers X) |
| `mysqlsh --python` (`--py`) | Python | auto-detect |
| `mysqlsh --sql` | SQL | auto-detect |
| `mysqlsh --mysql` | current mode | classic (3306) |
| `mysqlsh --mysqlx` | current mode | X (33060) |

- **Connection**: `mysqlsh --mysql serverconfig@localhost:33062` — the
  password is prompted interactively if not supplied, or embed it
  (`serverconfig:$PW@localhost:33062`), or use `--password=$PW`. The URI
  scheme also selects the protocol (`mysqlx://…` vs `mysql://…`).
  Remember: `serverconfig` works on the admin port 33062;
  `clusteradmin` cannot (no `SERVICE_CONNECTION_ADMIN` — step 5).
- **Protocol changes behavior**: auto-detect prefers X Protocol, which is
  fine for dba/cluster operations, but roles are not auto-activated over
  X (`CURRENT_ROLE()` → `NONE`) — force `--mysql` when session roles or
  classic-client semantics matter.
- **Running commands non-interactively**: `mysqlsh --sql -e "SELECT ..."`
  executes in the mode selected by the start flags and exits; scripts via
  `--file=<script>` (`.js`/`.py`/`.sql` per mode); add `--no-wizard` in
  non-interactive contexts so nothing blocks on a prompt; `--json` makes
  output machine-readable (handy for `cluster.status()` dumps you want to
  grep or diff).
- **Admin API usage** (JS mode):

  ```js
  shell.connect('serverconfig@localhost:33062')   // or \connect
  var c = dba.getCluster()
  c.status()        // the same payload get-cluster-status returns
  c.describe()
  ```

  Python mode uses snake_case: `dba.get_cluster().status()`.
  `cluster.status()` probes *members* on port 3306 — a member can be
  `MISSING` here while its local mysqld is alive.
- **Port/privilege recap**: 33062 admin interface (charm control channel,
  `serverconfig`), 3306 classic client, 33060 X. mysqlsh on K8s is on
  PATH in the workload container; on machines deployments it ships with
  the charmed-mysql snap (`charmed-mysql.mysqlsh` — see
  [machines-topology.md](references/machines-topology.md)).
- **mysqlsh refusals are contracts**: "Cannot perform operation on an
  healthy cluster because it can only be used to restore a cluster from
  quorum loss" is Group Replication's safety guard, not a bug.

### 8. Report

Summarize: cluster topology (members, roles, states), charm/juju/MySQL
versions, statuses with their *timestamps* (use `status-log` or debug-log
ordering when staleness matters), suspected root cause, and the next
probe. Separate the *trigger* (often transient) from the *defects* that
made it visible, state your confidence (verified / likely / hypothesis)
and what evidence would settle it. For signature-level interpretation,
load [failure-taxonomy.md](references/failure-taxonomy.md).

## References

Load on demand (all paths relative to this skill):

- [references/k8s-topology.md](references/k8s-topology.md) — step 3: full
  K8s container/path/port/secret map, FQDN scheme, control-plane vs member
  probes, X-protocol traps.
- [references/machines-topology.md](references/machines-topology.md) — the
  VM charm: snap layout, systemd/journalctl, paths, and how they differ
  from K8s.
- [references/charm-users.md](references/charm-users.md) — steps 5/7:
  user/role/privilege map and ready-made reproducer users.
- [references/bundle-anatomy.md](references/bundle-anatomy.md) — step 1
  (offline): file map of Test Observer bundles and crashdumps, grep
  cookbook, `db-dump.yaml` and `status-log` parsing.
- [references/hook-forensics.md](references/hook-forensics.md) — step 4:
  hook-context reconstruction, traceback frame analysis, retry/teardown
  semantics, deferred-event and uniter-operation analysis.
- [references/failure-taxonomy.md](references/failure-taxonomy.md) —
  steps 4/8: signature → cause → confirmation tables.
- `scripts/parse_uniter_ops.py` — step 4: measure uniter operation
  durations/gaps from `debug-log.txt` (`--help` for usage).
- `mysql-operators-source` skill — revision↔tag mapping, source reading at
  a deployed revision, branch selection, ops-version pinning (its
  `references/version-archaeology.md`).
