(revisions-312-313)=
# Revisions 312, 313

A new revision of Charmed MySQL has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 313             |  8.0.39       |        3.4.3+        |
|   `arm64`    | 312             |  8.0.39       |        3.4.3+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-vm>` before upgrading to this revision.

## Features

* [Upgraded MySQL](https://dev.mysql.com/doc/relnotes/mysql/8.0/en/news-8-0-37.html) from `v8.0.36` -> `v8.0.39` (see [Packaging](#packaging)) ([DPE-4573](https://warthogs.atlassian.net/browse/DPE-4573))
* Added support or ARM64 architecture ([PR #472](https://github.com/canonical/mysql-operator/pull/472)) 
* [Added support for Audit plugin](https://charmhub.io/mysql/docs/e-audit-logs) ([PR #488](https://github.com/canonical/mysql-operator/pull/488)) ([DPE-4366](https://warthogs.atlassian.net/browse/DPE-4366))
* [Added Awesome Prometheus Alert Rules](https://charmhub.io/mysql/docs/h-enable-alert-rules) (criticality) ([PR #493](https://github.com/canonical/mysql-operator/pull/493)) ([DPE-2477](https://warthogs.atlassian.net/browse/DPE-2477))
* [Add integration with COS Tempo HA](https://charmhub.io/mysql/docs/h-enable-tracing) ([DPE-5312](https://warthogs.atlassian.net/browse/DPE-5312))
* [New Terraform module](https://charmhub.io/mysql/docs/h-deploy-terraform) ([PR #540](https://github.com/canonical/mysql-operator/pull/540)) ([DPE-5627](https://warthogs.atlassian.net/browse/DPE-5627))
* Changed binlog retention period (one week by default) ([PR #503](https://github.com/canonical/mysql-operator/pull/503)) ([DPE-4247](https://warthogs.atlassian.net/browse/DPE-4247))
* Added support for re-scanning cluster for unit rejoin after node drain ([PR #462](https://github.com/canonical/mysql-operator/pull/462)) ([DPE-4118](https://warthogs.atlassian.net/browse/DPE-4118))
* Enable and use admin address/port for operator users  ([PR #516](https://github.com/canonical/mysql-operator/pull/516)) ([DPE-5178](https://warthogs.atlassian.net/browse/DPE-5178))

## Bug fixes

* Add warnings to destructive actions by ([PR #555](https://github.com/canonical/mysql-operator/pull/555)) ([DPE-5711](https://warthogs.atlassian.net/browse/DPE-5711))
* Fixed MySQL Group replication start logic during the juju refresh ([PR #546](https://github.com/canonical/mysql-operator/pull/546)) ([DPE-5941](https://warthogs.atlassian.net/browse/DPE-5941))
* Removed passwords from outputs and tracebacks ([PR #499](https://github.com/canonical/mysql-operator/pull/499)) ([DPE-4266](https://warthogs.atlassian.net/browse/DPE-4266))
* Fixed cluster metadata and instance state checks ([PR #482](https://github.com/canonical/mysql-operator/pull/482)) ([DPE-4850](https://warthogs.atlassian.net/browse/DPE-4850))
* Ensure username uniqueness ([PR #464](https://github.com/canonical/mysql-operator/pull/464)) ([DPE-4643](https://warthogs.atlassian.net/browse/DPE-4643))
* Set instance offline mode on restore ([PR #478](https://github.com/canonical/mysql-operator/pull/478)) ([DPE-4699](https://warthogs.atlassian.net/browse/DPE-4699))
* Added support for re-scanning cluster for unit rejoin after node drain ([PR #462](https://github.com/canonical/mysql-operator/pull/462)) ([DPE-4118](https://warthogs.atlassian.net/browse/DPE-4118))
* Fixes for backup logging ([PR #471](https://github.com/canonical/mysql-operator/pull/471)) ([DPE-4699](https://warthogs.atlassian.net/browse/DPE-4699))
* Fixed global-primary on endpoint ([PR #467](https://github.com/canonical/mysql-operator/pull/467)) ([DPE-4658](https://warthogs.atlassian.net/browse/DPE-4658))
* Skip set unknown config keys ([PR #532](https://github.com/canonical/mysql-operator/pull/532)) ([DPE-5628](https://warthogs.atlassian.net/browse/DPE-5628))
* Change key logs from debug->info ([PR #527](https://github.com/canonical/mysql-operator/pull/527)) ([DPE-4910](https://warthogs.atlassian.net/browse/DPE-4910))
* Fixed timeout node count query ([PR #528](https://github.com/canonical/mysql-operator/pull/528)) ([DPE-5582](https://warthogs.atlassian.net/browse/DPE-5582))
* Skip plugin install for not file found ([PR #524](https://github.com/canonical/mysql-operator/pull/524)) ([DPE-5540](https://warthogs.atlassian.net/browse/DPE-5540))
* Skip tls reconfiguration on unit teardown ([PR #522](https://github.com/canonical/mysql-operator/pull/522)) ([DPE-5493](https://warthogs.atlassian.net/browse/DPE-5493))
* Upgrade fix for admin-address enabled charm ([PR #520](https://github.com/canonical/mysql-operator/pull/520)) ([DPE-5178](https://warthogs.atlassian.net/browse/DPE-5178))
* Bump `cffi` to version 1.16.0 ([PR #549](https://github.com/canonical/mysql-operator/pull/549))
* Fixed use juju provided ip ([PR #558](https://github.com/canonical/mysql-operator/pull/558)) ([DPE-6105](https://warthogs.atlassian.net/browse/DPE-6105))
* Fixed regression on MAAS deployment ([PR #554](https://github.com/canonical/mysql-operator/pull/554)) ([DPE-6055](https://warthogs.atlassian.net/browse/DPE-6055))
* Add new VM reboot tests ([PR #534](https://github.com/canonical/mysql-operator/pull/534)) ([DPE-5415](https://warthogs.atlassian.net/browse/DPE-5415))
* Fixed starting group replication while waiting for upgrade ([PR #546](https://github.com/canonical/mysql-operator/pull/546)) ([DPE-5941](https://warthogs.atlassian.net/browse/DPE-5941))

**Full Changelog**: https://github.com/canonical/mysql-operator/compare/rev240...rev312

## Technical details

This section contains some technical details about the charm's contents and dependencies. 

If you are jumping over several stable revisions, check [previous release notes][All releases] before upgrading.

### Requirements and compatibility

This charm revision features the following changes in dependencies:
* (increased) MySQL version `v8.0.39`

This release of Charmed MySQL requires Juju `v.3.4.3` or `3.5.2+`. See the guide [How to upgrade Juju for a new database revision].

See the [system requirements] page for more details about software and hardware prerequisites.

### Packaging

This charm is based on the [`charmed-mysql` snap] Revision [113/114][snap rev113/114]. It packages:
- mysql-server-8.0: [8.0.39-0ubuntu0.22.04.1]
- mysql-router `v8.0.39`: [8.0.39-0ubuntu0.22.04.1]
- mysql-shell `v8.0.38`: [8.0.38+dfsg-0ubuntu0.22.04.1~ppa2]
- prometheus-mysqld-exporter `v0.14.0`: [0.14.0-0ubuntu0.22.04.1~ppa2]
- prometheus-mysqlrouter-exporter `v5.0.1`: [5.0.1-0ubuntu0.22.04.1~ppa1]
- percona-xtrabackup `v8.0.35`: [8.0.35-31-0ubuntu0.22.04.1~ppa3]

## Contact us
  
Charmed MySQL is an open source project that warmly welcomes community contributions, suggestions, fixes, and constructive feedback.  
* Raise software issues or feature requests on [**GitHub**](https://github.com/canonical/mysql-operator/issues)  
*  Report security issues through [**Launchpad**](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File)  
* Contact the Canonical Data Platform team through our [Matrix](https://matrix.to/#/#charmhub-data-platform:ubuntu.com) channel.

<!--Links-->
[system requirements]: https://charmhub.io/mysql/docs/r-system-requirements
[How to upgrade Juju for a new database revision]: https://charmhub.io/mysql/docs/h-upgrade-juju
[All releases]: https://charmhub.io/mysql/docs/r-releases

[snap rev113/114]: https://github.com/canonical/charmed-mysql-snap/releases/tag/rev114
[`charmed-mysql` snap]: https://snapcraft.io/charmed-mysql
[8.0.39-0ubuntu0.22.04.1]: https://launchpad.net/ubuntu/+source/mysql-8.0/8.0.39-0ubuntu0.22.04.1
[8.0.38+dfsg-0ubuntu0.22.04.1~ppa2]: https://launchpad.net/~data-platform/+archive/ubuntu/mysql-shell
[0.14.0-0ubuntu0.22.04.1~ppa2]: https://launchpad.net/~data-platform/+archive/ubuntu/mysqld-exporter
[5.0.1-0ubuntu0.22.04.1~ppa1]: https://launchpad.net/~data-platform/+archive/ubuntu/mysqlrouter-exporter
[8.0.35-31-0ubuntu0.22.04.1~ppa3]: https://launchpad.net/~data-platform/+archive/ubuntu/xtrabackup
