---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL K8s revisions 399–401 (MySQL 8.0.44): first s390x architecture support for amd64, arm64, and s390x."
---

(revisions-399-401)=
# Revisions 399, 400, 401

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 400             |  8.0.44       |        3.5.4+        |
|   `arm64`    | 399             |  8.0.44       |        3.5.4+        |
|   `s390x`    | 401             |  8.0.44       |        3.5.4+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:
- `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:672f20830d66678a3ece7285048700d6e52a9393202eb51e9749eb35031559c4`

## Highlights

This release is the first after the migration to a monorepo, shared by VM and K8s charms.
It is also the first one to make use of the [mysql-shell-client](https://github.com/canonical/mysql-shell-client/) package.

## Other features

* Use mysql-shell-client package by @sinclert-canonical in https://github.com/canonical/mysql-k8s-operator/pull/705
* Merge VM and K8s documentation by @a-velasco in https://github.com/canonical/mysql-operators/pull/95

### Bug fixes
* Fix charm tracing endpoint by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/139
* Improve k8s canonical DNS lookup by @gboutry in https://github.com/canonical/mysql-operators/pull/138
* Fix relation-broken services by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/152
* 8.0 - Fix: Do not decode tls-ca-chain received via S3 relation by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/161
* Fix spread installation path by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/175
* Create predefined roles after refresh by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/163

## New Contributors
* @gboutry made their first contribution in https://github.com/canonical/mysql-operators/pull/138

**Full Changelog**: https://github.com/canonical/mysql-operators/compare/mysql-k8s/rev351...mysql-k8s/rev401


