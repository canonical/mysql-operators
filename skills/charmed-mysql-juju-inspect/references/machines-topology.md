# Machines (VM) topology — snap, systemd, paths

Reference for `charmed-mysql-juju-inspect` when the deployment is the VM
charm (`mysql`, not `mysql-k8s`). Same interrogation sequence applies;
the substrate differs.

## Layout

The `mysql` charm runs on a Juju machine and manages everything through
the **`charmed-mysql` snap** (strict confinement, runs as `snap_daemon`):

```bash
juju ssh mysql/0
snap list charmed-mysql
snap services charmed-mysql
```

| Path | Contents |
|---|---|
| `/var/snap/charmed-mysql/common/var/log/mysql/` | `error.log`, `audit.log` + `archive_error/`, `archive_audit/` |
| `/var/snap/charmed-mysql/common/...` | revision-invariant data (`$SNAP_COMMON`) |
| `/var/snap/charmed-mysql/<revision>/...` | per-revision data (`$SNAP_DATA`) |
| `/var/snap/charmed-mysql/current/etc/mysqlrouter/` | router config (when router enabled) |

Snap aliases: `charmed-mysql.mysql` (→ `mysql`), `charmed-mysql.mysqlsh`,
`charmed-mysql.xtrabackup` / `.xbcloud` / `.xbstream`,
`charmed-mysql.mysql-pitr-helper`.

## Services

| Service | Notes |
|---|---|
| `charmed-mysql.mysqld` | The daemon (enabled/active normally) |
| `charmed-mysql.mysqld-exporter` | Disabled unless COS-related |
| `charmed-mysql.mysqlrouter-service` | Only in Charmed MySQL Router deployments; stopped on plain MySQL |

`mysqlrouter --bootstrap` bakes **absolute `$SNAP_DATA` paths** into
`mysqlrouter.conf` (`keyring_path`, `dynamic_state`). After a snap refresh
(revision changes), those paths point at the old revision directory:
AppArmor still allows *reading* it but blocks *writing* — the router
crashes on startup (`Could not open dynamic state file ... Permission
denied`), hits systemd's `StartLimitBurst` (5 crashes / 10s), and then
even a correct re-bootstrap can't start until the rate limiter resets.

## systemd layer (replaces pebble semantics)

- Real process stderr lives in the journal, **not** in charm/CI logs:
  ```bash
  juju ssh mysql/0 "sudo journalctl -u snap.charmed-mysql.mysqlrouter-service.service --no-pager -n 20 --output=cat"
  ```
- `snap start` returns exit 0 ("Started.") even when the service crashes
  immediately after; check `systemctl is-active` / `journalctl` instead.
- `snap stop` (→ `systemctl stop`) **resets** the `StartLimitBurst`
  failure counter — part of why stop→reconfigure→start recovery works.
- `snap.services[<name>]["active"]` reflects snapd's view, **not** whether
  the process is listening. Verify the port: `ss -tlnp | grep 6446` (router)
  or a SQL probe (mysqld).
- `snap ensure(state=Present)` succeeds at *any* installed revision —
  never use as a refresh-success check; verify the revision separately.

## Router checks (when a router is in the path)

```bash
juju ssh mysql/0 "sudo head -10 /var/snap/charmed-mysql/current/etc/mysqlrouter/mysqlrouter.conf"
# look for baked paths referencing a non-current revision:
#   keyring_path=/var/snap/charmed-mysql/230/var/lib/mysqlrouter/keyring
juju ssh mysql/0 "ss -tlnp | grep 6446"                 # classic rw port bound?
juju ssh mysql/0 "sudo tail -20 /var/snap/charmed-mysql/common/var/log/mysqlrouter/mysqlrouter.log"
```

Router signature: "No available servers found for PRIMARY routing" /
"Stop accepting connections" in the router log — metadata cache still
connecting to MySQL (can take >30s on slow hardware).

## Credentials

Same users as K8s (`root`, `serverconfig`, `clusteradmin`, ...); fetch via
`juju run mysql/0 get-password username=serverconfig`. Rotation on refresh
applies here too.

## What differs from K8s at a glance

| Concern | K8s | VM |
|---|---|---|
| Supervisor | Pebble (`/charm/bin/pebble`, default restart on failure) | systemd via snapd (`StartLimitBurst`) |
| Container isolation | 2 containers per pod | snap confinement |
| Log path | `/var/log/mysql/` | `/var/snap/charmed-mysql/common/var/log/mysql/` |
| Router data dir | n/a (charm-managed) | `$SNAP_DATA`-baked paths — refresh hazard |
| Process stderr | pebble/kubectl logs | `journalctl -u snap.charmed-mysql.*` |
