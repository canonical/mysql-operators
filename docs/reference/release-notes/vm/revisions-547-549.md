---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL VM revisions 547–549 (MySQL 8.0.45): fixes for scale-up race conditions, TLS deadlock and cluster endpoints."
---

(revisions-547-549)=
# Revisions 547, 548, 549

A new revision of Charmed MySQL has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version |
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 548             |  8.0.45       |        3.4.3+        |
|   `arm64`    | 549             |  8.0.45       |        3.4.3+        |
|   `s390x`    | 547             |  8.0.45       |        3.4.3+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-vm>` before upgrading to this revision.

## Highlights

- Fixed race conditions during scale-up, including concurrent restarts and empty peer sets
- Fixed a TLS race-condition deadlock
- Fixed cluster endpoints building

## What's Changed

### Features
* [DPE-10156] Release test from revision by @paulomach in https://github.com/canonical/mysql-operators/pull/523

### Bug fixes
* [DPE-11229] Fix empty peer set during scale-up by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/520
* Fix TLS race-condition deadlock by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/556
* Fix cluster-endpoints building by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/559
* [DPE-11831] Fix racing condition on concurrent restart and scale-up by @paulomach in https://github.com/canonical/mysql-operators/pull/575

**Full Changelog**: https://github.com/canonical/mysql-operators/compare/mysql/rev539...mysql/rev547
