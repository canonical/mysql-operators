---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL VM revisions 529–535 (MySQL 8.0.45): point-in-time backup recovery and Juju network spaces support added."
---

(revisions-529-535)=
# Revisions 529, 531, 535

A new revision of Charmed MySQL has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version |
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 529             |  8.0.45       |        3.4.3+        |
|   `arm64`    | 535             |  8.0.45       |        3.4.3+        |
|   `s390x`    | 531             |  8.0.45       |        3.4.3+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-vm>` before upgrading to this revision.


## What's Changed

This revision bumps MySQL version to 8.0.45 and many dependencies.
Also there are improvements on self healing, by treating new failure modes and trigger self-healing
independently from juju `update-status` hook.

### Features
* Merge VM and K8s documentation by @a-velasco in https://github.com/canonical/mysql-operators/pull/95
* Expose database endpoint in TF module by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/200
* Documented self healing cases by @paulomach in https://github.com/canonical/mysql-operators/pull/228
* Improve logging of get-cluster-status by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/304
* Define self-healing service by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/342
* Join expelled unit by @paulomach in https://github.com/canonical/mysql-operators/pull/359
* Only auto recover no_quorum if all peers are reachable by @paulomach in https://github.com/canonical/mysql-operators/pull/366
* Fixes for relations tests by @paulomach in https://github.com/canonical/mysql-operators/pull/374
* Enable metrics exporter by default by @Soundarya03 in https://github.com/canonical/mysql-operators/pull/407

### Bug fixes
* Fix keyerror when getting endpoints by @paulomach in https://github.com/canonical/mysql-operators/pull/66
* Fix charm tracing endpoint by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/139
* Fix relation-broken services by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/152
* Fix: Do not decode tls-ca-chain received via S3 relation by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/161
* Create predefined roles after refresh by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/163
* Fix cluster not initialized by @almeidaraul in https://github.com/canonical/mysql-operators/pull/119
* Handle stale primary on crash when joining peer by @paulomach in https://github.com/canonical/mysql-operators/pull/233
* Raise error properly if initialization fails by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/244
* Fix forcefull promotion to primary (force quorum) by @paulomach in https://github.com/canonical/mysql-operators/pull/262
* Fix Terraform expose block by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/312
* Anchor logs_retention_period validator regex by @paulomach in https://github.com/canonical/mysql-operators/pull/325
* Return after BlockedStatus when primary address missing in legacy relations by @paulomach in https://github.com/canonical/mysql-operators/pull/324
* Use non-stale data node for cluster belonging by @paulomach in https://github.com/canonical/mysql-operators/pull/345
* Fix node count target by @paulomach in https://github.com/canonical/mysql-operators/pull/340
* Fix user deletion on legacy by @paulomach in https://github.com/canonical/mysql-operators/pull/335
* Fix full cluster recovery when async related by @paulomach in https://github.com/canonical/mysql-operators/pull/332
* Conditional key deletion by @paulomach in https://github.com/canonical/mysql-operators/pull/355
* Safe auto-recover from no_quorum by @paulomach in https://github.com/canonical/mysql-operators/pull/338
* Fix create_endpoint_services skipping roles after 409 by @paulomach in https://github.com/canonical/mysql-operators/pull/323
* Increase sock file wait timeout on upgrade by @paulomach in https://github.com/canonical/mysql-operators/pull/390
* Fix TooManyPrimaries alert rule by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/408
* Avoid binary log rotation by @paulomach in https://github.com/canonical/mysql-operators/pull/441
* preserve type on config dict by @paulomach in https://github.com/canonical/mysql-operators/pull/388
* Release stale locks for failed/removed unit by @paulomach in https://github.com/canonical/mysql-operators/pull/445
* Fix TLS certificates race condition by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/467
* Fix to use tls-ca-chain received from S3 relation properly by @wallyworld in https://github.com/canonical/mysql-operators/pull/458

## New Contributors
* @gboutry made their first contribution in https://github.com/canonical/mysql-operators/pull/138
* @almeidaraul made their first contribution in https://github.com/canonical/mysql-operators/pull/119
* @carlcsaposs-canonical made their first contribution in https://github.com/canonical/mysql-operators/pull/278
* @wallyworld made their first contribution in https://github.com/canonical/mysql-operators/pull/458

**Full Changelog**: https://github.com/canonical/mysql-operators/compare/mysql/rev442...mysql/rev529
