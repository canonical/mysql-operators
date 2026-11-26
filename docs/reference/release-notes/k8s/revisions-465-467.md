---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL K8s revisions 465–467 (MySQL 8.0.45): fixes for scale-up race conditions, TLS deadlock and cluster endpoints."
---

(revisions-465-467)=

# Revisions 465, 466, 467

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version |
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 467             |  8.0.45       |        3.5.4+        |
|   `arm64`    | 465             |  8.0.45       |        3.5.4+        |
|   `s390x`    | 466             |  8.0.45       |        3.5.4+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:
 `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:824b302484f83dbbd2cf4506f620a48e53f20053f6ff3c57aa6123e121705bfc`

## Highlights

- Fixed race conditions during scale-up, including concurrent restarts and empty peer sets
- Fixed a TLS race-condition deadlock
- Fixed cluster endpoints building

## What's Changed

### Features
- [DPE-10156] Release test from revision by @paulomach in <https://github.com/canonical/mysql-operators/pull/523>

### Bug fixes
- [DPE-11229] Fix empty peer set during scale-up by @astrojuanlu in <https://github.com/canonical/mysql-operators/pull/520>
- Fix TLS race-condition deadlock by @sinclert-canonical in <https://github.com/canonical/mysql-operators/pull/556>
- Fix cluster-endpoints building by @sinclert-canonical in <https://github.com/canonical/mysql-operators/pull/559>
- [DPE-11831] Fix racing condition on concurrent restart and scale-up by @paulomach in <https://github.com/canonical/mysql-operators/pull/575>

**Full Changelog**: <https://github.com/canonical/mysql-operators/compare/mysql-k8s/rev457...mysql-k8s/rev465>
