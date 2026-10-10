---
name: charmed-mysql-juju-inspect
description: >
  Inspects a live Charmed MySQL (mysql or mysql-k8s) deployment through
  Juju: reads juju status, fetches true cluster topology via actions, maps
  containers/ports/pebble services, obtains credentials, reads charm and
  mysqld logs, and queries MySQL with the mysql client or mysqlsh.
  Use when inspecting a live deployment: a blocked, waiting,
  error, or degraded unit, a bug reproduction or debugging session, or
  a user request to check cluster, unit, or MySQL health. Ground truth
  before theorizing about root cause.
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.5.0"
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

### 1. Read `juju status` (and what it cannot tell you)

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

- **Read app status AND unit status separately.** They are set by
  different code paths. App `blocked` with unit `active` (e.g. app-level
  relation blocks) and app `maintenance` + unit `active "Primary"` are
  both real and mean different things than either alone.
- The unit message "Primary" means *local Group Replication primary*,
  not cluster-set primary.
- Statuses are the charm's *opinion*: derived on update-status, lagging
  reality by up to the update-status interval, and masking each other
  (blocked overwritten within one interval — see Gotchas). Never time
  anything against `juju status` — poll actions (step 2) instead.
- A unit parked in **`unknown`** right after deploy means its hooks never
  completed. On K8s the classic cause is a deploy without `--trust` (the
  RBAC race — the charm service account can't read `nodes` at cluster
  scope); the log signature and fix are in the `juju-cli` skill's Deploy
  section.

### 2. Get cluster truth from actions

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
mysqld. Router chaining (router below router) is known-problematic.

### 4. Credentials

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

### 5. Logs

Workload-side (mysqld, audit):

```bash
juju ssh -m <model> --container mysql mysql-k8s/0 \
  "tail -50 /var/log/mysql/error.log; ls /var/log/mysql/archive_error/"
# error.log may be empty between rotations; recent history is in archive_error/*.gz (zcat)
```

Charm-side (hooks, events, tracebacks):

```bash
juju debug-log -m <model> --ms --level DEBUG --include unit-mysql-k8s-0 --replay --no-tail
juju debug-log -m <model> -i unit-mysql-k8s-0 -n 0          # replay all + follow
```

- Every hook process starts with `ops <version> up and running.` — use as
  a process-start marker when correlating.
- Scheduled dispatches appear as `Emitting Juju event rotate_mysql_logs.`
  (per minute) and `heal_mysql_cluster.` (every ~2m) — normal, not errors.
- On controllers where kubectl works, `kubectl logs <pod> -c charm` gives
  the same content fresher (but is lost on container restart); juju
  debug-log survives restarts (model logging config permitting — check
  `juju model-config logging-config`).

### 6. Direct SQL and mysqlsh

Quick SQL probe via the mysql client (credentials from step 4; on K8s
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
  `clusteradmin` cannot (no `SERVICE_CONNECTION_ADMIN` — step 4).
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

### 7. Verify what is deployed

Cheap and decisive before deep debugging:

```bash
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

### 8. Report

Summarize: cluster topology (members, roles, states), charm/juju/MySQL
versions, statuses with their *timestamps* (use `status-log` or debug-log
ordering when staleness matters), suspected root cause, and the next
probe. For signature-level interpretation, load the
`charmed-mysql-log-autopsy` skill's `references/failure-taxonomy.md`.

## Gotchas

- **juju CLI mechanics**: options before the target, remote commands as
  one quoted string, the snap's `/tmp` restriction, `juju exec --unit`
  limits, model/controller selection — all live in the `juju-cli` skill;
  do not re-derive them here.
- **kubectl may be unusable** (API unreachable from your workstation).
  Everything above is achievable via juju ssh/exec/actions.
- **`get-password` vs secrets**: `get-password` on any unit returns the
  app-wide user passwords (they are app-level secrets), fine for
  interrogation.
- **`juju status` statuses are opinions**: unit status derives from
  peer-databag `member-state`/`member-role` on update-status; blocked
  statuses set by other handlers get overwritten within one interval.
  A "blocked that healed itself" was masked, not fixed.
- **`update-status-hook-interval`** is a legitimate observation dial (e.g.
  `juju model-config update-status-hook-interval=15s` to see masking
  happen, or 30m to freeze reactions during experiments) — remember to
  restore it.

## References

- [references/k8s-topology.md](references/k8s-topology.md) — step 3: full
  K8s container/path/port/secret map, FQDN scheme, control-plane vs member
  probes, X-protocol traps.
- [references/machines-topology.md](references/machines-topology.md) — the
  VM charm: snap layout, systemd/journalctl, paths, and how they differ
  from K8s.
- [references/charm-users.md](references/charm-users.md) — step 4/6:
  user/role/privilege map and ready-made reproducer users.
