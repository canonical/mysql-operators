---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL K8s revisions 423–425 (MySQL 8.0.44): self-healing improvements, safer quorum recovery, and Terraform expose support."
---

(revisions-423-425)=
# Revisions 423, 424, 425

A new revision of Charmed MySQL for K8s has been published in the `8.0/edge` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/edge).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version |
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 423             |  8.0.44       |        3.5.2+        |
|   `arm64`    | 425             |  8.0.44       |        3.5.2+        |
|   `s390x`    | 424             |  8.0.44       |        3.5.2+        |

OCI image resources:
- `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:824b302484f83dbbd2cf4506f620a48e53f20053f6ff3c57aa6123e121705bfc`

## Highlights

- Added a dedicated self-healing service for more automated recovery scenarios.
- Improved recovery behavior for quorum loss, full outages, and expelled units.
- Added Terraform support for the `expose` block when deploying MySQL K8s.

## Other features

* Add a dedicated self-healing service and document supported recovery cases.
* Add a guide to access MySQL Shell directly on a unit for troubleshooting and advanced administration.
* Update the charm to use `mysql-shell-client` v1 and `pydantic` v2.
* Add Terraform support for deployment-time `expose` configuration.
* Expose the `database` endpoint in the Terraform module.
* Move the K8s charm to the rootless container packaging model.

## Bug fixes

* Make automatic no-quorum recovery safer by only attempting it when all peers are reachable.
* Allow expelled units to rejoin the cluster automatically after they lose membership.
* Improve full cluster recovery when async replication is related.
* Fix stale-primary handling when joining a peer after a crash.
* Improve peer FQDN and address resolution for unit and endpoint discovery.
* Fix endpoint service creation after Kubernetes `409` conflicts.
* Fix cleanup of legacy `mysql-root` users when relations are broken.
* Return immediately after setting blocked status when the cluster primary address is unavailable.
* Tighten validation for `logs_retention_period` and fix the Pebble `MYSQLD_PARENT_PID` environment type.

**Full Changelog**: https://github.com/canonical/mysql-operators/compare/mysql-k8s/rev400...mysql-k8s/rev425
