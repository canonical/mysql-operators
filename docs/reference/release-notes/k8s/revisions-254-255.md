---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL K8s revisions 254 and 255 (MySQL 8.0.41), fixing root user password reset initialization behavior."
---

(revisions-254-255)=
# Revisions 254, 255

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 255             |  8.0.41       |        3.5.4+        |
|   `arm64`    | 254             |  8.0.41       |        3.5.4+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:
- `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:089fc04dd2d6f1559161ddf4720c1e06559aeb731ecae57b050c9c816e9833e9`

## Features

* [DPE-1531](https://warthogs.atlassian.net/browse/DPE-1531) Avoid using initialize-insecure and instead use init-file to reset root user's password by @shayancanonical in [#596](https://github.com/canonical/mysql-k8s-operator/pull/596)
* [DPE-6487](https://warthogs.atlassian.net/browse/DPE-6487) Point-in-time recovery support by @paulomach and @Zvirovyi  in [#600](https://github.com/canonical/mysql-k8s-operator/pull/600)
* [DPE-3830](https://warthogs.atlassian.net/browse/DPE-3830) Default to `paxos` single leader by @paulomach in [#604](https://github.com/canonical/mysql-k8s-operator/pull/604)
* [DPE-6312](https://warthogs.atlassian.net/browse/DPE-6312) Add security policy by @paulomach  in [#605](https://github.com/canonical/mysql-k8s-operator/pull/605)
* [DPE-7534](https://warthogs.atlassian.net/browse/DPE-7534) use absolute fqdn for replication and consumers by @paulomach in [#618](https://github.com/canonical/mysql-k8s-operator/pull/618)

## Bug fixes

* [DPE-6733](https://warthogs.atlassian.net/browse/DPE-6733)  test for DNS availability by @paulomach in [#612](https://github.com/canonical/mysql-k8s-operator/pull/612)

**Full Changelog**: https://github.com/canonical/mysql-k8s-operator/compare/rev240...rev255

## Requirements and compatibility

* Recommended Juju version: `v3.6.3+`

See the [system requirements](https://charmhub.io/mysql-k8s/docs/r-system-requirements) for more details about Juju versions and other software and hardware prerequisites.