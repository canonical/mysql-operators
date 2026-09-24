# K8s topology — containers, paths, ports, secrets

Reference for `charmed-mysql-juju-inspect` steps 3–6 (mysql-k8s).

## Pod layout

Each unit is one pod, two containers (both entered via pebble as PID 1):

```
pod mysql-k8s-<n>
├── container "charm"    ← juju ssh <unit> lands here (root)
│   └── /var/lib/juju/agents/unit-<app>-<n>/charm/   deployed charm source
│       ├── src/, lib/, templates/, scripts/
│       └── venv/                                     python interpreter + deps
└── container "mysql"    ← juju ssh --container mysql <unit> (workload)
    ├── /charm/bin/pebble                             service supervisor
    ├── /var/lib/mysql/                               datadir (Juju storage mount)
    ├── /var/log/mysql/{error.log,audit.log}          + archive_error/, archive_audit/ (*.gz)
    ├── /etc/mysql/mysql.conf.d/z-custom.cnf          charm-written mysqld config
    ├── /usr/bin/mysqlsh, /usr/bin/mysql, /usr/sbin/mysqld
    └── xtrabackup/xbcloud/xbstream                   backup tooling
```

- The ROCK is built from the `charmed-mysql` snap — same component
  versions as the VM charm.
- Charm-container stdout *is* the juju-log stream (ops attaches a
  JujuLogHandler to the root logger; plain `logging` from libs reaches it).

## Pebble services (workload container)

`/charm/bin/pebble services` / `pebble plan` (plan = effective config):

| Service | Default startup | Purpose |
|---|---|---|
| `mysqld` | enabled | The daemon; runs directly with `--datadir=/var/lib/mysql --log-error=/var/log/mysql/error.log`; `kill-delay: 24h` |
| `mysql` | enabled | `tail -F` of error.log (log streaming helper) |
| `mysqld_exporter` | disabled | Prometheus exporter (enabled via COS relations) |
| `mysql-pitr-helper-collector` | disabled | Binlog collection for PITR (enabled with S3 backups) |

Pebble's default `on-failure` is `restart`: a killed mysqld is restarted
automatically within seconds unless explicitly user-stopped (`pebble stop`).
This matters enormously for failure injection (see fault-injection skill).

## Ports and connection classes

| Port | Protocol | Used by |
|---|---|---|
| 3306 | classic MySQL | Applications, member probes (mysqlsh `cluster.status()` → other members), `mysql` CLI, mysql.connector |
| 33060 | X protocol | mysqlsh default when auto-detecting (`--sql` prefers X if plugin enabled) |
| **33062** | classic, admin interface | **The charm's control channel** (mysqlsh via pebble exec, user `serverconfig`) |

Two distinct connection classes — the single most important fact for
connection-related debugging:

1. **Control connections**: charm → mysqld admin port 33062. Used by
   `get-cluster-status`, `add_instance_to_cluster`, and every other
   charm-side mysqlsh operation.
2. **Member probe connections**: mysqlsh, *inside* `cluster.status()`,
   probing each member's **port 3306**. These surface as
   `shellconnecterror` entries in the status topology payload.

Corollaries (each learned the hard way):

- `SET GLOBAL max_connections=1` does **not** block the charm (33062 is
  not subject to `max_connections`) — but it *does* lock out every other
  client including root via socket, and only the pod's own restart
  reliably unlocks it (per-server variable; fixing "from another unit"
  only fixes that unit).
- `admin_address` is read-only at runtime (`ERROR 1238`); the admin
  listener binds the unit FQDN, **not** loopback — connecting to
  `localhost:33062` is refused (`error 111`). Script against
  `--host=<unit FQDN> --port=33062`.
- The charm never uses the X socket (`/var/run/mysqld/mysqlx.sock`) for
  cluster operations — moving it changes nothing.
- `clusteradmin` lacks `SERVICE_CONNECTION_ADMIN` → cannot log in on 33062
  (`Access denied; you need (at least one of) the SERVICE_CONNECTION_ADMIN`).
  Use `serverconfig`.

## Addresses

- Unit FQDNs: `<app>-<n>.<app>-endpoints.<model>.svc.cluster.local`
  (the `-endpoints` headless service per unit).
- K8s Services created by the charm: `<app>-primary` and `<app>-replicas`
  (created at start since [DPE-9622]; relation setup resolves their DNS).
- Pod IPs from `juju status --format json`
  (`.applications.<app>.units.<unit>.address`) — reachable from any host
  that can route to the cluster (e.g. for `mysql.connector` from a test
  runner, which always uses classic protocol).
- App-level access: `juju run` actions target any unit; the charm roams
  reads to `instance_address` (follows the primary across failovers).

## Secrets and credentials

- All charm-internal passwords live in one peer-relation secret (label
  `database-peers.mysql-k8s.app`): `root-password`,
  `server-config-password`, `cluster-admin-password`,
  `monitoring-password`, `backups-password`.
- `juju run <unit> get-password username=<user>` returns them (app-level).
- Per-relation user credentials are separate secrets (label pattern
  `database.<relation-id>.user.secret`).
- **Passwords rotate on every charm refresh/redeploy.**

## Deployed-source verification

```bash
juju ssh mysql-k8s/0 \
  "grep -rn '<marker>' /var/lib/juju/agents/unit-mysql-k8s-0/charm/src/ /var/lib/juju/agents/unit-mysql-k8s-0/charm/lib/charms/mysql/v0/"
```

Charm-lib ERROR strings may come from venv site-packages (e.g.
`mysql_shell`), not the repo — search there when a log line has no repo hit.
