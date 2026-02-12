(revision-153)=
# Revision 153

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 153             |  8.0.36       |        3.4.3+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

## Features

* New workload version [MySQL 8.0.36](https://dev.mysql.com/doc/relnotes/mysql/8.0/en/news-8-0-36.html)
* [Async replication between clouds](https://charmhub.io/mysql-k8s/docs/h-async-deployment) [[DPE-2959](https://warthogs.atlassian.net/browse/DPE-2959)]
* [Add COS Tempo tracing support](https://charmhub.io/mysql-k8s/docs/h-enable-tracing) [[#424](https://github.com/canonical/mysql-k8s-operator/pull/424)][[DPE-4368](https://warthogs.atlassian.net/browse/DPE-4368)]
* Add [experimental_max_connections](https://charmhub.io/mysql-k8s/configuration?channel=8.0/candidate#experimental-max-connections) config [[#425](https://github.com/canonical/mysql-k8s-operator/pull/425)][[DPE-3706](https://warthogs.atlassian.net/browse/DPE-3706)]
* Latest ROCK latest version [[DPE-3717](https://warthogs.atlassian.net/browse/DPE-3717)] 
* Internal disable operator mode [[DPE-2184](https://warthogs.atlassian.net/browse/DPE-2184)]
* TLS CA chain support [[PR#383](https://github.com/canonical/mysql-k8s-operator/pull/383)]
* All the functionality from [previous revisions](https://charmhub.io/mysql-k8s/docs/r-releases)

## Bug fixes

* Updated shared libraries
* Applied the latest Juju secrets related fixes
* Fixed Sunbeam: charm is trying fail to set `report_host` on scale up [#435](https://github.com/canonical/mysql-k8s-operator/pull/435),  [DPE-3896](https://warthogs.atlassian.net/browse/DPE-3896)
* Skip config change when no pebble connection in [#445](https://github.com/canonical/mysql-k8s-operator/pull/445), [DPE-4768](https://warthogs.atlassian.net/browse/DPE-4768) 
* Fix restart for single-unit in [#438](https://github.com/canonical/mysql-k8s-operator/pull/438), [DPE-4411](https://warthogs.atlassian.net/browse/DPE-4411)

**Full Changelog**: https://github.com/canonical/mysql-k8s-operator/compare/rev127...rev153

## Inside the charms
  
* Charmed MySQL K8s ships MySQL `8.0.36-0ubuntu0.22.04.1`
* CLI mysql-shell updated to `8.0.36+dfsg-0ubuntu0.22.04.1~ppa4`
* Backup tools xtrabackup/xbcloud is `8.0.35-30`
* The Prometheus mysqld-exporter is `0.14.0-0ubuntu0.22.04.1~ppa2`
* K8s charms [based on our ROCK OCI](https://github.com/canonical/charmed-mysql-rock) (Ubuntu LTS  `22.04.4`) `mysql-image` resource-revision `111`
* Principal charms support the latest Ubuntu 22.04 LTS only

## Technical notes
  
* Upgrade (`juju refresh`) is possible from revision 75+
* [Creating Async replication](https://charmhub.io/mysql-k8s/docs/h-async-deployment) under significant write load to Primary could lead to MySQL DB deadlock and replication setup failures, more details in official [charm bugreport](https://github.com/canonical/mysql-k8s-operator/issues/399) and [MySQL bug](https://bugs.mysql.com/bug.php?id=114624&thanks=sub).
* Use this operator together with modern operator [MySQL Router K8s](https://charmhub.io/mysql-router-k8s)
* Please check restrictions from [previous release notes](https://charmhub.io/mysql-k8s/docs/r-releases)  
* Ensure [the charm requirements](https://charmhub.io/mysql-k8s/docs/r-system-requirements) met.