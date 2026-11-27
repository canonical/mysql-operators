---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL VM revisions 550-552 (MySQL 8.4.13)"
---

(revisions-550-552)=
# Revisions 550, 551, 552

A new revision of Charmed MySQL VM has been published in the `8.4/stable` channel on [Charmhub](https://charmhub.io/mysql?channel=8.4/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version |
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 551             |  8.4.13       |        3.6.0+        |
|   `arm64`    | 552             |  8.4.13       |        3.6.0+        |
|   `s390x`    | 550             |  8.4.13       |        3.6.0+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-vm>` before upgrading to this revision.

## Highlights

- Modernized the stack: MySQL 8.4.13, built with Ubuntu 26.06 and Python 3.14.
- Refactored codebase to a single-kernel architecture: behavior must be consistent between K8s and VM.
- Migrated to modern refresh V3 implementation.
- Migrated to modern TLS V4 charm interface.
- Migrated to modern ops V3 framework.
- Hardened security by moving the K8s operator to be rootless.
- Split operator storage between archive, data, logs and temp.
- Standardized MySQL Exporter lifecycle: will be enabled at start-up time.
- Standardized operator system users.

## Breaking changes

- Drop support for PITR backups (planning to restore this functionality in the near future).
- Drop support for Juju 2 environments.
- Drop support for legacy interfaces:
    - `mysql`
    - `mysql-root`
- Renamed TLS interface:
    - `certificates` -> `client-certificates` / `peer-certificate`
- Standardized configuration options:
    - `binlog_retention_days` -> `binlog-retention-days`
    - `logs_audit_policy` -> `logs-audit-policy`
    - `logs_retention_period` -> `logs-retention-period`
    - `experimental-max-connections` -> `max-connections`
- Standardized operator system users:
    - `serverconfig` -> `charmed-operator`
    - `clusteradmin` -> `charmed-replication`
    - `monitoring` -> `charmed-stats`
    - `backups` -> `charmed-backup`
