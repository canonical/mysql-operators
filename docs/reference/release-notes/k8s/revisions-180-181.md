(revisions-180-181)=
# Revisions 180, 181

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 180             |  8.0.37       |        3.4.3+        |
|   `arm64`    | 181             |  8.0.37       |        3.4.3+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

## Features

* Upgraded MySQL from `v8.0.36` -> `v8.0.37` (see [Packaging](#packaging))
* Added support or ARM64 architecture ([PR #448](https://github.com/canonical/mysql-k8s-operator/pull/448)) 
* Added support for Audit plugin ([PR #474](https://github.com/canonical/mysql-k8s-operator/pull/474)) ([DPE-4970](https://warthogs.atlassian.net/browse/DPE-4970))
*  Add first Awesome Alert Rules ([PR #469](https://github.com/canonical/mysql-k8s-operator/pull/469)) ([DPE-2477](https://warthogs.atlassian.net/browse/DPE-2477))
* Added support for re-scanning cluster for unit rejoin after node drain ([PR #433](https://github.com/canonical/mysql-k8s-operator/pull/433)) ([DPE-4118](https://warthogs.atlassian.net/browse/DPE-4118))
* Changed binlog retention period (one week by default) ([PR #478](https://github.com/canonical/mysql-k8s-operator/pull/478)) ([DPE-4247](https://warthogs.atlassian.net/browse/DPE-4247))

## Bug fixes

* Removed passwords from outputs and tracebacks ([PR #473](https://github.com/canonical/mysql-k8s-operator/pull/473)) ([DPE-4266](https://warthogs.atlassian.net/browse/DPE-4266))
* Fixed intermittent issue on AKS deployments (unknown/idle state) ([PR #458](https://github.com/canonical/mysql-k8s-operator/pull/458)) ([DPE-4850](https://warthogs.atlassian.net/browse/DPE-4850))
* Strip passwords from command execute output and tracebacks ([PR #473](https://github.com/canonical/mysql-k8s-operator/pull/473)) ([DPE-4266](https://warthogs.atlassian.net/browse/DPE-4266))
* Address drained units rejoining the cluster with a new PV ([PR #433](https://github.com/canonical/mysql-k8s-operator/pull/433)) ([DPE-4118](https://warthogs.atlassian.net/browse/DPE-4118))
* Ensure username uniqueness ([PR #439](https://github.com/canonical/mysql-k8s-operator/pull/439)) ([DPE-4643](https://warthogs.atlassian.net/browse/DPE-4643))
* Backup stabilization fixes ([PR #444](https://github.com/canonical/mysql-k8s-operator/pull/444)) ([DPE-4699](https://warthogs.atlassian.net/browse/DPE-4699))
* Idempotent configure method ([PR #451](https://github.com/canonical/mysql-k8s-operator/pull/451)) ([DPE-4800](https://warthogs.atlassian.net/browse/DPE-4800))
* Show global-primary on endpoint ([PR #440](https://github.com/canonical/mysql-k8s-operator/pull/440)) ([DPE-4658](https://warthogs.atlassian.net/browse/DPE-4658))
* Fix metrics-endpoint created on scale up ([PR #483](https://github.com/canonical/mysql-k8s-operator/pull/483))

**Full Changelog**: https://github.com/canonical/mysql-k8s-operator/compare/rev153...rev180

## Requirements and compatibility

This section contains some technical details about the charm's contents and dependencies. 

If you are jumping over several stable revisions, check [previous release notes](https://charmhub.io/mysql-k8s/docs/r-releases) before upgrading.

* Recommended Juju version:  `3.5.2+`
  *  See the guide: [How to upgrade Juju for a new database revision].

See the [system requirements](https://charmhub.io/mysql-k8s/docs/r-system-requirements) page for more details about software and hardware prerequisites.

### Packaging
This charm is based on the [`charmed-mysql` rock]  (CharmHub  `mysql-image` resource-revision `113`). It packages:
- mysql-server-8.0: [8.0.37-0ubuntu0.22.04.1]
- mysql-router `v8.0.37`: [8.0.37-0ubuntu0.22.04.1]
- mysql-shell `v8.0.37`: [8.0.37+dfsg-0ubuntu0.22.04.1~ppa3]
- prometheus-mysqld-exporter `v0.14.0`: [0.14.0-0ubuntu0.22.04.1~ppa2]
- prometheus-mysqlrouter-exporter `v5.0.1`: [5.0.1-0ubuntu0.22.04.1~ppa1]
- percona-xtrabackup `v8.0.35`: [8.0.35-31-0ubuntu0.22.04.1~ppa3]

<!--Links-->
[`charmed-mysql` rock]: https://github.com/canonical/charmed-mysql-rock/pkgs/container/charmed-mysql
[8.0.37-0ubuntu0.22.04.1]: https://launchpad.net/ubuntu/+source/mysql-8.0/8.0.37-0ubuntu0.22.04.3
[8.0.37+dfsg-0ubuntu0.22.04.1~ppa3]: https://launchpad.net/~data-platform/+archive/ubuntu/mysql-shell
[0.14.0-0ubuntu0.22.04.1~ppa2]: https://launchpad.net/~data-platform/+archive/ubuntu/mysqld-exporter
[5.0.1-0ubuntu0.22.04.1~ppa1]: https://launchpad.net/~data-platform/+archive/ubuntu/mysqlrouter-exporter
[8.0.35-31-0ubuntu0.22.04.1~ppa3]: https://launchpad.net/~data-platform/+archive/ubuntu/xtrabackup