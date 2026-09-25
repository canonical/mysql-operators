# Charm users, roles, and privileges

Reference for `charmed-mysql-juju-inspect` steps 4 and 6. Who's who inside
a Charmed MySQL server, and which users make good reproducers.

## Internal charm users

| User | Purpose | Notes |
|---|---|---|
| `root` | Full SQL access | Password in the peer secret (`root-password`) |
| `serverconfig` | The charm's control connection | **Only user with admin-port 33062 access** (`SERVICE_CONNECTION_ADMIN`) |
| `clusteradmin` | Cluster administration via mysqlsh | Lacks `SERVICE_CONNECTION_ADMIN` — cannot log in on 33062 |
| `monitoring` | mysqld_exporter | Password also in the exporter's env (`EXPORTER_PASS`) |
| `backups` | xtrabackup operations | Used with the S3 integrator relation |
| `mysqlrouter` / `charmed_router` | Router credential-rotation role | 8.0 sends `mysqlrouter`; 8.4 renamed to `charmed_router` |
| `mysql_innodb_cluster_<id>` / `mysql_innodb_cs_<...>` | Group Replication / ClusterSet internals | Do not touch |

All passwords fetchable via `juju run <unit> get-password username=<user>`
(values are app-level; rotate on every refresh).

## Application-facing roles (created by the charm)

Predefined roles (from `lib/charms/mysql/v0/mysql.py`):

```
charmed_dba > charmed_ddl > charmed_dml        (hierarchy)
charmed_dba > charmed_stats, charmed_backup, charmed_read
```

- Users created **without** `extra-user-roles` get **direct grants**
  (`GRANT ALL PRIVILEGES ON <db>.*`) — no roles involved.
- Users created **with** `extra-user-roles` (e.g. `charmed_dba`,
  `charmed_read`, or a database-scoped `charmed_dba_<db>_<NN>`) get
  privileges **only from the role** (`CREATE USER` + `GRANT <role> TO`).

## The X Protocol role-activation trap

`activate_all_roles_on_login=1` (the charm's default) activates roles at
login **on the classic protocol only**:

| Protocol | Port | Roles auto-activated at login? |
|---|---|---|
| Classic | 3306 | Yes |
| X Protocol | 33060 | **No — `CURRENT_ROLE()` returns `NONE`** |

`mysqlsh --sql` **auto-detects and prefers X Protocol** when the X plugin
is enabled. Consequence: queries that fail with
`ERROR 1142: SELECT command denied` for role-based users may simply be
running over X with dormant roles. Fixes: prepend `SET ROLE ALL;` to the
session, or force classic with `mysqlsh --mysql` (or use the `mysql` CLI /
`mysql.connector`, which always speak classic).

Verify which protocol was used: `SELECT CURRENT_ROLE();` — `NONE` on X
(or genuinely no roles). Compare across forced protocols:

```bash
mysqlsh --mysql  -h 127.0.0.1 -u <user> -p<pass> --sql -e "SELECT CURRENT_ROLE();"
mysqlsh --mysqlx -h 127.0.0.1 -u <user> -p<pass> --sql -e "SELECT CURRENT_ROLE();"
```

Cosmetic mysqlsh stderr noise to ignore: `Cannot set LC_ALL to locale
en_US.UTF-8`, and the password-on-command-line `[WARNING]`.

## Ready-made reproducer users

Before creating test users, use what's always deployed:

| User | Direct grants | Role | Good for reproducing |
|---|---|---|---|
| `charmed-stats` | `USAGE ON *.*` only | `charmed_stats` (RELOAD, PROCESS, REPLICATION CLIENT, SELECT on performance_schema) | **Role-only privilege failures** — anything real fails without the role |
| `charmed-backup` | `USAGE ON *.*` only | `charmed_backup` | Backup-privilege paths |
| `charmed-operator` | `ALL ON *.* WITH GRANT OPTION` | none | Direct-grant baseline (no role involvement) |

`charmed-stats` is the ideal X-vs-classic reproducer: with roles dormant
(X Protocol) real queries fail; with `SET ROLE ALL` or classic protocol
they succeed.

## Useful SQL probes

```sql
SELECT CURRENT_ROLE();
SHOW GRANTS FOR '<user>'@'%';
SHOW GRANTS FOR '<user>'@'%' USING <role_name>;      -- grants including role privileges
SELECT from_user, to_user FROM mysql.role_edges;      -- role hierarchy
SELECT user, host FROM mysql.user WHERE user LIKE 'charmed%';
SELECT member_id, member_host, member_state, member_role
  FROM performance_schema.replication_group_members;  -- live GR view
SELECT @@super_read_only, @@activate_all_roles_on_login,
       @@group_replication_single_primary_mode;
```
