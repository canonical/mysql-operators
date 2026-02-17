(revision-99)=
# Revision 99

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 99              |  8.0.34       |        3.1.6+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

## Features

* [Add Juju 3 support](https://charmhub.io/mysql-k8s/docs/r-system-requirements) (Juju 2 is still supported) [[DPE-1790](https://warthogs.atlassian.net/browse/DPE-1790)]
* Peer secrets are now stored in [Juju secrets](https://juju.is/docs/juju/manage-secrets) [[DPE-1813](https://warthogs.atlassian.net/browse/DPE-1813)]
* Charm [minor upgrades](https://charmhub.io/mysql-k8s/docs/h-upgrade-minor) and [minor rollbacks](https://charmhub.io/mysql-k8s/docs/h-rollback-minor) [[DPE-2206](https://warthogs.atlassian.net/browse/DPE-2206)]
* [Profiles configuration](https://charmhub.io/mysql-k8s/docs/r-profiles) support [[DPE-2154](https://warthogs.atlassian.net/browse/DPE-2154)]
* Workload updated to [MySQL 8.0.34](https://dev.mysql.com/doc/relnotes/mysql/8.0/en/news-8-0-34.html) [[DPE-2426](https://warthogs.atlassian.net/browse/DPE-2426)]
* Support `juju expose` [[DPE-1215](https://warthogs.atlassian.net/browse/DPE-1215)]
* Add the first Prometheus alert rule (COS Loki) [[PR#244](https://github.com/canonical/mysql-k8s-operator/pull/244)]
* New documentation:
  * {ref}`Architecture (HLD/LLD) <architecture>`
  * {ref}`Upgrade section <refresh>`
  * {ref}`Release Notes <release-notes>`
  * {ref}`Requirements <system-requirements>`
  * {ref}`Users <users>`
  * {ref}`Statuses <charm-statuses>`
  * {ref}`Development <charm-development>`
  * {ref}`Testing reference <charm-testing>`
  * {ref}`Legacy charm <legacy-charm>`
  * {ref}`Contacts <contacts>`

## Bug fixes

Canonical Data issues are now public on both [Jira](https://warthogs.atlassian.net/jira/software/c/projects/DPE/issues/) and [GitHub](https://github.com/canonical/mysql-k8s-operator/issues) platforms.<br/>[GitHub Releases](https://github.com/canonical/mysql-k8s-operator/releases) provide a detailed list of bug fixes/PRs/Git commits for each revision.<br/>Highlights for the current revision:

* [DPE-1919](https://warthogs.atlassian.net/browse/DPE-1919) Fixed GKE [deployment support](https://charmhub.io/mysql-k8s/docs/h-deploy-gke)
* [DPE-1519](https://warthogs.atlassian.net/browse/DPE-1519) Stabilized integration with mysql-route-k8s
* [DPE-2069](https://warthogs.atlassian.net/browse/DPE-2069) Fixed MySQL max_connections auto tune
* [DPE-2225](https://warthogs.atlassian.net/browse/DPE-2225) Fixed MySQL memory allocation (use K8s `Allocatable` memory instead of `free` + consider `group_replication_message_cache_size`)
* [DPE-988](https://warthogs.atlassian.net/browse/DPE-988) Fixed standby units (9+ cluster members are waiting to join the cluster)
* [DPE-2352](https://warthogs.atlassian.net/browse/DPE-2352) Start mysqld-exporter on COS relation only + restart upon monitoring password change
* [DPE-1512](https://warthogs.atlassian.net/browse/DPE-1512) Auto-generate `username`/`database` when config values are empty (for legacy `mysql` relation)
* [DPE-2178](https://warthogs.atlassian.net/browse/DPE-2178) Stop configuring mysql user `root@%` (removed as no longer necessary)

**Full Changelog**: https://github.com/canonical/mysql-k8s-operator/compare/rev75...rev99

## What is inside the charms

* Charmed MySQL K8s ships the latest MySQL “8.0.34-0ubuntu0.22.04.1”
* CLI mysql-shell updated to "8.0.34-0ubuntu0.22.04.1~ppa1"
* Backup tools xtrabackup/xbcloud  updated to "8.0.34-29"
* The Prometheus mysqld-exporter is "0.14.0-0ubuntu0.22.04.1~ppa1"
* K8s charms [based on our](https://github.com/orgs/canonical/packages?tab=packages&q=charmed) ROCK OCI (Ubuntu LTS “22.04” - ubuntu:22.04-based)
* Principal charms supports the latest LTS series “22.04” only.
* Subordinate charms support LTS “22.04” and “20.04” only.

## Technical notes

* Upgrade (`juju refresh`) from the old-stable revision 75 to the current-revision 99 is **NOT** supported!!! The [upgrade](https://charmhub.io/mysql-k8s/docs/h-upgrade) functionality is new and supported for revision 99+ only!
* Please check additionally [the previously posted restrictions](https://charmhub.io/mysql-k8s/docs/r-revision-75).
* Ensure [the charm requirements](https://charmhub.io/mysql-k8s/docs/r-system-requirements) met.

## How to reach us

If you would like to chat with us about your use-cases or ideas, you can reach us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/data-platform) or [Discourse](https://discourse.charmhub.io/). Check all other contact details [here](https://charmhub.io/mysql-k8s/docs/r-contacts).

Consider [opening a GitHub issue](https://github.com/canonical/mysql-k8s-operator/issues) if you want to open a bug report.<br/>[Contribute](https://github.com/canonical/mysql-k8s-operator/blob/main/CONTRIBUTING.md) to the project!
