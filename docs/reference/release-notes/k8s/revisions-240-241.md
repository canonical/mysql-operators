(revisions-240-241)=
# Revisions 240, 241

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 240             |  8.0.41       |        3.5.4+        |
|   `arm64`    | 241             |  8.0.41       |        3.5.4+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:
- `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:089fc04dd2d6f1559161ddf4720c1e06559aeb731ecae57b050c9c816e9833e9`

## Features

* DPE-5063 **Update MySQL to v8.0.41** by @shayancanonical in https://github.com/canonical/mysql-k8s-operator/pull/566 , https://github.com/canonical/mysql-k8s-operator/pull/574
* DPE-5656 log rotation new options by @paulomach in https://github.com/canonical/mysql-k8s-operator/pull/568
* DPE-6651 Update rock tag for new builds with updated percona packages by @shayancanonical in https://github.com/canonical/mysql-k8s-operator/pull/594

## Bug fixes

* DPE-6137 insecure password calls removal by @paulomach in https://github.com/canonical/mysql-k8s-operator/pull/553
* DPE-4375 Add cluster manual re-join handler by @sinclert-canonical in https://github.com/canonical/mysql-k8s-operator/pull/560
* DPE-6521 Add missing check and wait for pebble calls by @paulomach in https://github.com/canonical/mysql-k8s-operator/pull/571
* DPE-6485 Manage `mysqld` directly by @paulomach in https://github.com/canonical/mysql-k8s-operator/pull/575
* DPE-6666 Remove async-replication test workaround by @sinclert-canonical in https://github.com/canonical/mysql-k8s-operator/pull/588
* DPE-5164 ensure failed bootstrap cleanup by @paulomach in https://github.com/canonical/mysql-k8s-operator/pull/592

**Full Changelog**: https://github.com/canonical/mysql-k8s-operator/compare/rev210...rev240

## New contributors

* @sinclert-canonical made their first contribution in https://github.com/canonical/mysql-k8s-operator/pull/539

## Requirements and compatibility

* Recommended Juju version: `v3.6.3+`