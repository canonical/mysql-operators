(revision-127)=
# Revision 127

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 127             |  8.0.35       |        3.1.6+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

## Features

* Updated workload to [MySQL 8.0.35](https://dev.mysql.com/doc/relnotes/mysql/8.0/en/news-8-0-35.html) in [#360](https://github.com/canonical/mysql-k8s-operator/pull/360)
* Juju 3.1.7+ support in [#2037120](https://bugs.launchpad.net/juju/+bug/2037120)
* [DPE-3402](https://warthogs.atlassian.net/browse/DPE-3402) Update TLS test lib and test charm in [#370](https://github.com/canonical/mysql-k8s-operator/pull/370)
* [DPE-3617](https://warthogs.atlassian.net/browse/DPE-3617) Add CA chain support in [#383](https://github.com/canonical/mysql-k8s-operator/pull/383)
* Add [Allure Report beta](https://canonical.github.io/mysql-k8s-operator/) in [#366](https://github.com/canonical/mysql-k8s-operator/pull/366)
* All the functionality from [the previous revisions](https://charmhub.io/mysql-k8s/docs/r-releases)

## Bug fixes

* [DPE-3547](https://warthogs.atlassian.net/browse/DPE-3547) Fixed mitigations for container restart  in [#377](https://github.com/canonical/mysql-k8s-operator/pull/377)
* [DPE-3389](https://warthogs.atlassian.net/browse/DPE-3389) Fixed support for rollbacks with incompatible data dir in [#385](https://github.com/canonical/mysql-k8s-operator/pull/385)
* [DPE-2919](https://warthogs.atlassian.net/browse/DPE-2919) Fixed pod labels update on preemptive switchover in [#367](https://github.com/canonical/mysql-k8s-operator/pull/367)
* [DPE-3265](https://warthogs.atlassian.net/browse/DPE-3265) Refactored lib secrets in [#362](https://github.com/canonical/mysql-k8s-operator/pull/362)
* [DPE-2758](https://warthogs.atlassian.net/browse/DPE-2758) Fixed messaging when no bucket + ceph testing in [#332](https://github.com/canonical/mysql-k8s-operator/pull/332)
* [DPE-3027](https://warthogs.atlassian.net/browse/DPE-3027) Fixed retry policy for is_mysqld_running in [#356](https://github.com/canonical/mysql-k8s-operator/pull/356)
* Fixed typo in secrets marker in [#380](https://github.com/canonical/mysql-k8s-operator/pull/380)
* Fixed parallel backup tests in [#375](https://github.com/canonical/mysql-k8s-operator/pull/375)
* Removed colon from logrotate file path in [#351](https://github.com/canonical/mysql-k8s-operator/pull/351)

**Full Changelog**: https://github.com/canonical/mysql-k8s-operator/compare/rev113...rev127

# What is inside the charms

* Charmed MySQL K8s ships MySQL “`8.0.35-0ubuntu0.22.04.1`”
* CLI mysql-shell updated to "`8.0.33-0ubuntu0.22.04.1~ppa1`"
* Backup tools xtrabackup/xbcloud  updated to "`8.0.35-30`"
* The Prometheus mysqld-exporter is "`0.14.0-0ubuntu0.22.04.1~ppa1`"
* K8s charms [based on our](https://github.com/orgs/canonical/packages?tab=packages&q=charmed) ROCK OCI (Ubuntu 22.04 LTS - ubuntu:22.04-based)
* Principal charms supports the latest Ubuntu 22.04 LTS only

## Technical notes

* Upgrade (`juju refresh`) is possible from revision 75+
* Use this operator together with a modern operator "[MySQL Router K8s](https://charmhub.io/mysql-router-k8s)"
* Please check additionally [the previously posted restrictions](https://charmhub.io/mysql-k8s/docs/r-releases)
* Ensure [the charm requirements](https://charmhub.io/mysql-k8s/docs/r-system-requirements) met

## Project and community

Charmed MySQL K8s is an official distribution of MySQL. It’s an open-source project that welcomes community contributions, suggestions, fixes and constructive feedback.

* [Read our Code of Conduct](https://ubuntu.com/community/code-of-conduct)
* [Join the Discourse forum](https://discourse.charmhub.io/tag/mysql-k8s)
* [Contribute](https://github.com/canonical/mysql-k8s-operator/blob/main/CONTRIBUTING.md) and report [issues](https://github.com/canonical/mysql-k8s-operator/issues/new/choose)
* Explore all [Canonical Data Fabric solutions](https://canonical.com/data)
* [Contact us](https://charmhub.io/mysql-k8s/docs/r-contacts) for all further questions