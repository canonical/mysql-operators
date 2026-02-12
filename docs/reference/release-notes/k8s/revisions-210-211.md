(revisions-210-211)=
# Revisions 210, 211

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 210             |  8.0.39       |        3.5.4+        |
|   `arm64`    | 211             |  8.0.39       |        3.5.4+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:

* `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:aa4d9b21673d2c6e4db3dc943179bae95dd8d355790b68e4e0610da9513ee6c9`

## Features

* **Updated MySQL to `v8.0.39`** ([PR #488](https://github.com/canonical/mysql-k8s-operator/pull/488)) ([DPE-4573](https://warthogs.atlassian.net/browse/DPE-4573))
* **Added fully-featured terraform module** ([PR #522](https://github.com/canonical/mysql-k8s-operator/pull/522)) ([DPE-5627](https://warthogs.atlassian.net/browse/DPE-5627))
  * See also: [How to deploy on Terraform](https://charmhub.io/mysql-k8s/docs/h-deploy-terraform)
* Updated COS alert rule descriptions ([PR #519](https://github.com/canonical/mysql-k8s-operator/pull/519)) ([DPE-5659](https://warthogs.atlassian.net/browse/DPE-5659))
  * See also: [How to enable alert rules](https://charmhub.io/mysql-k8s/docs/h-enable-alert-rules), 
* Bumped juju versions ([PR #517](https://github.com/canonical/mysql-k8s-operator/pull/517))
  * `v2.9.50` -> `v2.9.51`
  * `v3.4.5` -> `v3.5.4`
* Integrated with Tempo HA and tested relay support of tracing traffic through `grafana-agent-k8s` ([PR #518](https://github.com/canonical/mysql-k8s-operator/pull/518)) ([DPE-5312](https://warthogs.atlassian.net/browse/DPE-5312))
* Adopted admin address throughout charm ([PR #502](https://github.com/canonical/mysql-k8s-operator/pull/502)) ([DPE-5178](https://warthogs.atlassian.net/browse/DPE-5178))
* Avoid ambiguous service selector when multiple `mysql` apps in a model have the same cluster-name ([PR #501](https://github.com/canonical/mysql-k8s-operator/pull/501)) ([DPE-4861](https://warthogs.atlassian.net/browse/DPE-4861))
* Ensure that uninitialized variable not referenced in `_is_cluster_blocked` helper ([PR #507](https://github.com/canonical/mysql-k8s-operator/pull/507)) ([DPE-5481](https://warthogs.atlassian.net/browse/DPE-5481))
* Recover from pod restarts during cluster creation during setup ([PR #499](https://github.com/canonical/mysql-k8s-operator/pull/499))
* Added timeout on node count query ([PR #514](https://github.com/canonical/mysql-k8s-operator/pull/514)) ([DPE-5582](https://warthogs.atlassian.net/browse/DPE-5582))

### Bug fixes
* Fixed unit-initialized test may break when run too early ([PR #491](https://github.com/canonical/mysql-k8s-operator/pull/491)) ([DPE-5209](https://warthogs.atlassian.net/browse/DPE-5209))
* Common credentials fixture and `exec` timeout workaround ([PR #493](https://github.com/canonical/mysql-k8s-operator/pull/493)) ([DPE-5210](https://warthogs.atlassian.net/browse/DPE-5210))
* Fixed /database requested wait container ([PR #500](https://github.com/canonical/mysql-k8s-operator/pull/500)) ([DPE-5385](https://warthogs.atlassian.net/browse/DPE-5385))
* Attempted to stabilize failing integration tests ([PR #496](https://github.com/canonical/mysql-k8s-operator/pull/496))
* Add test to ensure correct k8s endpoints created for clusters with the same name ([PR #508](https://github.com/canonical/mysql-k8s-operator/pull/508))
* Add check to ensure peer databag populated before reconciling mysqld exporter pebble layers ([PR #505](https://github.com/canonical/mysql-k8s-operator/pull/505)) ([DPE-5417](https://warthogs.atlassian.net/browse/DPE-5417))
* Add base in test_multi_relations to workaround libjuju bug ([PR #506](https://github.com/canonical/mysql-k8s-operator/pull/506)) ([DPE-5480](https://warthogs.atlassian.net/browse/DPE-5480))

**Full Changelog**: https://github.com/canonical/mysql-k8s-operator/compare/rev180...rev210