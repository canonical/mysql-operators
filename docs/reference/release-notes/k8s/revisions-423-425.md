---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL K8s revisions 423–425 (MySQL 8.0.45)"
---

(revisions-423-425)=
# Revisions 423, 424, 425

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 423             |  8.0.45       |        3.5.4+        |
|   `arm64`    | 424             |  8.0.45       |        3.5.4+        |
|   `s390x`    | 424             |  8.0.45       |        3.5.4+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:
- `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:824b302484f83dbbd2cf4506f620a48e53f20053f6ff3c57aa6123e121705bfc`

## Highlights

- Added a dedicated self-healing service for more automated recovery scenarios.
- Improved recovery behavior for quorum loss, full outages, and expelled units.
- Added Terraform support for the `expose` block when deploying MySQL K8s.
- Bump MySQL to 8.0.45

## What's Changed
### Features
* [MISC] 8.0 - Expose database endpoint in TF module by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/200
* [DPE-9675] doc: self healing cases by @paulomach in https://github.com/canonical/mysql-operators/pull/228
* [docs] Add mysql-shell access page by @paulomach in https://github.com/canonical/mysql-operators/pull/231
* [MISC] Remove feature rollback from incompatible by @paulomach in https://github.com/canonical/mysql-operators/pull/246
* [MISC] 8.0 - Update promote workflow by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/242
* [MISC] 8.0 - Bump pydantic library to v2 by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/260
* [MISC] Fix condition for publishing Allure results by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/289
* [MISC] (8.0/edge) Improve logging of get-cluster-status by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/304
* [MISC] 8.0 - Bump mysql-shell-client to v1 by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/328
* [MISC] 8.0 - Migrate to snap package by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/346
* [DPE-7872] 8.0 - Define self-healing service by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/342
* [DPE-9966] Join expelled unit (8.0/edge) by @paulomach in https://github.com/canonical/mysql-operators/pull/359
* [MISC] only auto recover no_quorum if all peers are reachable by @paulomach in https://github.com/canonical/mysql-operators/pull/366
* [misc] (8.0/edge) fixes for relations tests by @paulomach in https://github.com/canonical/mysql-operators/pull/374
### Bug fixes
* [DPE-9167] Fix cluster not initialized 8.0 by @almeidaraul in https://github.com/canonical/mysql-operators/pull/119
* [MISC] 8.0 - Fix COS-related docs by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/207
* [DPE-9791] Handle stale primary on crash when joining peer by @paulomach in https://github.com/canonical/mysql-operators/pull/233
* [fix] Add robustness to peer address resolution by @paulomach in https://github.com/canonical/mysql-operators/pull/209
* [MISC] [VM] Raise error properly if initialization fails (8.0) by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/244
* [MISC] fix forcefull promotion to primary (force quorum) by @paulomach in https://github.com/canonical/mysql-operators/pull/262
* [MISC] 8.0 - Cleanup K8s legacy permissions fix [revert] by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/287
* [MISC] More FQDN resolution fixes by @astrojuanlu in https://github.com/canonical/mysql-operators/pull/292
* [MISC] Fix release test runner selectors. by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/296
* [DPE-10193] 8.0 - Fix Terraform expose block by @sinclert-canonical in https://github.com/canonical/mysql-operators/pull/312
* [MISC] Quote MYSQLD_PARENT_PID in Pebble env dict by @paulomach in https://github.com/canonical/mysql-operators/pull/326
* [MISC] Anchor logs_retention_period validator regex by @paulomach in https://github.com/canonical/mysql-operators/pull/325
* [MISC] Return after BlockedStatus when primary address missing in legacy relations by @paulomach in https://github.com/canonical/mysql-operators/pull/324
* [DPE-10337] Use non-stale data node for cluster belonging by @paulomach in https://github.com/canonical/mysql-operators/pull/345
* [MISC] Fix node count target by @paulomach in https://github.com/canonical/mysql-operators/pull/340
* [MISC] fix user deletion on legacy by @paulomach in https://github.com/canonical/mysql-operators/pull/335
* [MISC] Fix full cluster recovery when async related by @paulomach in https://github.com/canonical/mysql-operators/pull/332
* [MISC] 8.0 - update prometheus_scrape lib rev by @chanchiwai-ray in https://github.com/canonical/mysql-operators/pull/360
* [MISC] Add missing trust by @paulomach in https://github.com/canonical/mysql-operators/pull/362
* [MISC] conditional key deletion by @paulomach in https://github.com/canonical/mysql-operators/pull/355
* [DPE-9259] Safe auto-recover from no_quorum by @paulomach in https://github.com/canonical/mysql-operators/pull/338
* [MISC] Fix create_endpoint_services skipping roles after 409 by @paulomach in https://github.com/canonical/mysql-operators/pull/323
* [DPE-10340] (8.0/edge) Bump loki_push_api lib by @paulomach in https://github.com/canonical/mysql-operators/pull/370

## New Contributors
* @almeidaraul made their first contribution in https://github.com/canonical/mysql-operators/pull/119
* @carlcsaposs-canonical made their first contribution in https://github.com/canonical/mysql-operators/pull/278

**Full Changelog**: https://github.com/canonical/mysql-operators/compare/mysql-k8s/rev399...mysql-k8s/rev423
