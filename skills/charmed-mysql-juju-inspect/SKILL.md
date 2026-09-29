---
name: charmed-mysql-juju-inspect
description: >
  Interrogate a live Charmed MySQL (mysql or mysql-k8s) deployment through
  Juju to assess health and pinpoint problems: read juju status correctly
  (app vs unit statuses, agent vs workload), fetch true cluster topology via
  actions, map containers/ports/pebble services, obtain credentials, read
  charm and mysqld logs, and run direct SQL when needed. Use when a deployed
  Charmed MySQL unit is blocked, waiting, error, degraded, suspected
  unhealthy, or the user asks to "check the cluster", "why is unit X
  <status>", "is MySQL healthy", or reports connectivity/replication
  problems on a reachable deployment. Not for working from logs without
  live access (prefer log-autopsy) or for deliberately breaking/reproducing
  failures (prefer fault-injection).
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.1.0"
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
juju status -m <model>                       # human view
juju status -m <model> --format json         # for parsing (see below)
```

Reading rules:

- **Read app status AND unit status separately.** They are set by
  different code paths. App `blocked` with unit `active` (e.g. app-level
  relation blocks) and app `maintenance` + unit `active "Primary"` are
  both real and mean different things than either alone.
- Agent status lives at `applications.<app>.units.<unit>.juju-status.current`
  in JSON (**not** `agent-status`); workload status at
  `workload-status.current`. Agent `executing` continuously (with workload
  active) suggests scheduled out-of-band dispatches — healthy workload,
  busy agent.
- The status **message** is free text set by whichever handler last ran;
  "Primary" on a unit means *local Group Replication primary*, not
  cluster-set primary.
- Statuses lag reality by up to the update-status interval (default 5m).
  Never time anything against `juju status` — poll actions instead.

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

Expected pebble services: `mysqld` (enabled/active — the daemon),
`mysql` (log tail helper), `mysqld_exporter` (disabled unless COS-related),
`mysql-pitr-helper-collector` (disabled unless PITR/binlogs configured).
`pebble plan` shows the effective layer config — ground truth vs the
charm's layer code. Note `mysqld` runs *directly* (`--datadir=/var/lib/mysql`),
with `kill-delay: 24h` (SIGTERM → graceful shutdown takes a long time).

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

### 6. Direct SQL when needed

```bash
PW=$(...)  # from get-password
juju ssh -m <model> --container mysql mysql-k8s/0 \
  "mysql -u root -p$PW -e 'select member_id, member_state, member_role from performance_schema.replication_group_members'"
```

Useful probes: `replication_group_members` (live GR view),
`SELECT @@super_read_only, @@group_replication_single_primary_mode;`,
`SHOW GRANTS FOR '<user>'@'%';`, `SELECT CURRENT_ROLE();` (returns `NONE`
over X Protocol when roles aren't auto-activated — see
[charm-users.md](references/charm-users.md)). mysqlsh protocol note:
`mysqlsh --sql` auto-detects and prefers X Protocol; force classic with
`--mysql`.

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
  is often just an older deployed revision.

### 8. Report

Summarize: cluster topology (members, roles, states), charm/juju/MySQL
versions, statuses with their *timestamps* (use `status-log` or debug-log
ordering when staleness matters), suspected root cause, and the next
probe. For signature-level interpretation, load the log-autopsy skill's
`references/failure-taxonomy.md`.

## Gotchas

- **juju CLI**: options go *before* the target (`juju ssh --container mysql
  mysql-k8s/0 "<cmd>"`); pass remote commands as ONE quoted string (arg
  splitting mangles pipes/redirects); juju is a snap and cannot read/write
  `/tmp` — keep bundles/downloads in the project dir or `$HOME`; confirm
  the starred controller/model before acting (`juju controllers`, `juju models`).
- **`juju exec --unit` runs in the charm container** with hook-like env
  (`CHARM_DIR`, `JUJU_UNIT_NAME`); it cannot run python heredocs or
  multi-line `-c` payloads — one-liners only, or `juju ssh`.
- **kubectl may be unusable** (API unreachable from your workstation).
  Everything above is achievable via juju ssh/exec/actions. Where k8s
  access exists on controller-hosted rigs it may be `sudo k8s kubectl`
  (no bare kubectl, no microk8s).
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
