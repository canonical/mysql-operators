(revisions-366-367)=
# Revisions 366, 367

A new revision of Charmed MySQL has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 366             |  8.0.41       |        3.4.3+        |
|   `arm64`    | 367             |  8.0.41       |        3.4.3+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-vm>` before upgrading to this revision.

## Features

* **Update MySQL to v8.0.41** in https://github.com/canonical/mysql-operator/pull/606 by @shayancanonical 
* [DPE-6651](https://warthogs.atlassian.net/browse/DPE-6651) Update snap revisions to new builds with updated percona packages in https://github.com/canonical/mysql-operator/pull/622 by @shayancanonical 
* [DPE-5656](https://warthogs.atlassian.net/browse/DPE-5656) New options for log rotation in https://github.com/canonical/mysql-operator/pull/597 by @paulomach 
* [DPE-4375](https://warthogs.atlassian.net/browse/DPE-4375) Add operator managed self-rejoin in https://github.com/canonical/mysql-operator/pull/592 by @sinclert-canonical 
* [DPE-5588](https://warthogs.atlassian.net/browse/DPE-5588) Check against invalid arch in https://github.com/canonical/mysql-operator/pull/563 by @sinclert-canonical 

## Bug fixes

* [DPE-6137](https://warthogs.atlassian.net/browse/DPE-6137) Refactor for password safety by @paulomach in https://github.com/canonical/mysql-operator/pull/579
* [DPE-4375](https://warthogs.atlassian.net/browse/DPE-4375) Add cluster manual re-join handler by @sinclert-canonical in https://github.com/canonical/mysql-operator/pull/592
* [DPE-6666](https://warthogs.atlassian.net/browse/DPE-PE-666) Remove async-replication test workaround by @sinclert-canonical in https://github.com/canonical/mysql-operator/pull/619
* fix: dpe-6695 fix race on legacy mysql by @paulomach in https://github.com/canonical/mysql-operator/pull/624
* [DPE-6488](https://warthogs.atlassian.net/browse/DPE-PE-648) Address slow `mysqld` start upon unit reboot by @shayancanonical in https://github.com/canonical/mysql-operator/pull/615

**Full Changelog**: https://github.com/canonical/mysql-operator/compare/rev312...rev366

## Technical details

This section contains some technical details about the charm's contents and dependencies. 

If you are jumping over several stable revisions, check [previous release notes](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/) before upgrading.

### Requirements and compatibility

This charm revision features the following changes in dependencies:
* (increased) MySQL version to `v8.0.41`
* (increased) [Snap](https://github.com/canonical/charmed-mysql-snap/) revision 138/139
 
```{note}
This release of Charmed MySQL requires Juju `v.3.4.3` or `3.5.2+`. 

See: {ref}`How to upgrade Juju for a new database revision <upgrade-juju>`
```