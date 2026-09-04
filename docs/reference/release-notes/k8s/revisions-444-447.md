---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL K8s revisions 444-447 (MySQL 8.0.45)"
---

(revisions-444-447)=
# Revisions 444, 446, 447

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version |
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 444             |  8.0.45       |        3.5.4+        |
|   `arm64`    | 447             |  8.0.45       |        3.5.4+        |
|   `s390x`    | 446             |  8.0.45       |        3.5.4+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:
- `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:824b302484f83dbbd2cf4506f620a48e53f20053f6ff3c57aa6123e121705bfc`

## Highlights

- Fixed issue when changing dynamic config would trigger rolling restart
- Avoid file descriptor starvation from binlog rotation


OCI image resources:
- `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:824b302484f83dbbd2cf4506f620a48e53f20053f6ff3c57aa6123e121705bfc`


## What's Changed

### Features
* Enable metrics exporter by default by @Soundarya03 in https://github.com/canonical/mysql-operators/pull/407
* Juju proxy aware K8s operator by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/439

### Bug fixes
* Increase sock file wait timeout on upgrade by @paulomach in https://github.com/canonical/mysql-operators/pull/390
* Fix TooManyPrimaries alert rule by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/408
* Avoid binary log rotation by @paulomach in https://github.com/canonical/mysql-operators/pull/441
* Preserve type on config dict by @paulomach in https://github.com/canonical/mysql-operators/pull/388
* Release stale locks for failed/removed unit by @paulomach in https://github.com/canonical/mysql-operators/pull/445
* Fix TLS certificates race condition by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/467
* Fix to use tls-ca-chain received from S3 relation properly by @wallyworld in https://github.com/canonical/mysql-operators/pull/458

## New Contributors
* @wallyworld made their first contribution in https://github.com/canonical/mysql-operators/pull/458

**Full Changelog**: https://github.com/canonical/mysql-operators/compare/mysql-k8s/rev423...mysql-k8s/rev444
