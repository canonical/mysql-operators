---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL K8s revisions 468-470 (MySQL 8.4.13)"
---

(revisions-468-470)=
# Revisions 468, 469, 470

A new revision of Charmed MySQL K8s has been published in the `8.4/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.4/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version |
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 470             |  8.4.13       |        3.6.0+        |
|   `arm64`    | 468             |  8.4.13       |        3.6.0+        |
|   `s390x`    | 469             |  8.4.13       |        3.6.0+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:
 `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:8a9314656a8820ffe5c06db4cb396cff3247844ccc70839a6d9bf390579936db`

## Highlights

- Modernized the stack: MySQL 8.4.13, built with Ubuntu 26.06 and Python 3.14.
- Refactored codebase to a single-kernel architecture: behavior must be consistent between K8s and VM.
- Migrated to modern refresh V3 implementation.
- Migrated to modern TLS V4 charm interface.
- Migrated to modern ops V3 framework.
- Migrated to modern OTEL collector integration, instead of Grafana Agent.
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
