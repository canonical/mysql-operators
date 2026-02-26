---
myst:
  html_meta:
    description: "Release notes for Charmed MySQL K8s revisions 342–344 (MySQL 8.0.44): first s390x architecture support for amd64, arm64, and s390x."
---

(revisions-342-344)=
# Revisions 342, 343, 344

A new stable revision of Charmed MySQL for K8s has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql-k8s?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 343             |  8.0.44       |        3.5.4+        |
|   `arm64`    | 344             |  8.0.44       |        3.5.4+        |
|   `s390x`    | 342             |  8.0.44       |        3.5.4+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-k8s>` before upgrading to this revision.

OCI image resources:
- `mysql-image=ghcr.io/canonical/charmed-mysql@sha256:672f20830d66678a3ece7285048700d6e52a9393202eb51e9749eb35031559c4`

## Highlights

- **Bumped MySQL version to 8.0.44**
- Added support for **IBM s390x architecture**
- Added support for **pre-defined roles**

## Other features

* [DPE-7802](https://warthogs.atlassian.net/browse/DPE-7802) Update MySQL to 8.0.42 & add s390x arch by @carlcsaposs-canonical in [#636](https://github.com/canonical/mysql-k8s-operator/pull/636)
* [DPE-7404](https://warthogs.atlassian.net/browse/DPE-7404) promote to primary on unit scope by @paulomach in [#646](https://github.com/canonical/mysql-k8s-operator/pull/646)
* [DPE-7322](https://warthogs.atlassian.net/browse/DPE-7322) Support predefined roles by @sinclert-canonical in [#635](https://github.com/canonical/mysql-k8s-operator/pull/635)
* [DPE-8050](https://warthogs.atlassian.net/browse/DPE-8050) Backup action cluster checks by @sinclert-canonical in [#654](https://github.com/canonical/mysql-k8s-operator/pull/654)
* [DPE-7322](https://warthogs.atlassian.net/browse/DPE-7322) Tweak database DBA role naming by @sinclert-canonical in [#658](https://github.com/canonical/mysql-k8s-operator/pull/658)
* [DPE-8291](https://warthogs.atlassian.net/browse/DPE-8291) Extend Terraform deployment docs by @sinclert-canonical in [#667](https://github.com/canonical/mysql-k8s-operator/pull/667)
* [DPE-7242](https://warthogs.atlassian.net/browse/DPE-7242) Add multi-cluster refresh docs by @a-velasco in [#670](https://github.com/canonical/mysql-k8s-operator/pull/670)
* [DPE-7656](https://warthogs.atlassian.net/browse/DPE-7656) error.log to stdout by @paulomach in [#691](https://github.com/canonical/mysql-k8s-operator/pull/691)
* [DPE-8877](https://warthogs.atlassian.net/browse/DPE-8877) Upgrade MySQL to 8.0.44 by @astrojuanlu in [#706](https://github.com/canonical/mysql-k8s-operator/pull/706)
* [DPE-9006](https://warthogs.atlassian.net/browse/DPE-9006) Allow more connection errors before blocking host by @paulomach in [#711](https://github.com/canonical/mysql-k8s-operator/pull/711)

## Bug fixes

* [DPE-7648](https://warthogs.atlassian.net/browse/DPE-7648) Fix access to not populated instance label by @sinclert-canonical in [#629](https://github.com/canonical/mysql-k8s-operator/pull/629)
* fix: DPE-7497 ensure early logging_provider relation wont break init by @paulomach in [#616](https://github.com/canonical/mysql-k8s-operator/pull/616)
* [DPE-7705](https://warthogs.atlassian.net/browse/DPE-7705) Remove peers-relation-changed hook by @sinclert-canonical in [#640](https://github.com/canonical/mysql-k8s-operator/pull/640)
* [DPE-7421](https://warthogs.atlassian.net/browse/DPE-7421) Fix MySQL legacy interface relation by @sinclert-canonical in [#639](https://github.com/canonical/mysql-k8s-operator/pull/639)
* Fix alert rules screenshot by @a-velasco in [#657](https://github.com/canonical/mysql-k8s-operator/pull/657)
* Fix OSM integration test by @sinclert-canonical in [#659](https://github.com/canonical/mysql-k8s-operator/pull/659)
* fix: enabling trust for deployments by @deusebio in [#666](https://github.com/canonical/mysql-k8s-operator/pull/666)
* Bump Jubilant-backports to v1.4.0 by @sinclert-canonical in [#665](https://github.com/canonical/mysql-k8s-operator/pull/665)
* DPE-7649 Replace `event.set_results(success=False)` with `event.fail()` in action get-cluster-status by @astrojuanlu in [#673](https://github.com/canonical/mysql-k8s-operator/pull/673)
* Replace charmcraft-test by spread by @sinclert-canonical in [#685](https://github.com/canonical/mysql-k8s-operator/pull/685)
* Set Jubilant logging to WARNING by @sinclert-canonical in [#693](https://github.com/canonical/mysql-k8s-operator/pull/693)
* [DPE-8600](https://warthogs.atlassian.net/browse/DPE-8600) Point certificates charm to 1/stable by @sinclert-canonical in [#692](https://github.com/canonical/mysql-k8s-operator/pull/692)
* Fix initialization by @astrojuanlu in [#697](https://github.com/canonical/mysql-k8s-operator/pull/697)
* Fix allure-report publication by @sinclert-canonical in [#695](https://github.com/canonical/mysql-k8s-operator/pull/695)
* fix: escape role_name on creation by @paulomach in [#694](https://github.com/canonical/mysql-k8s-operator/pull/694)
* [DPE-8924](https://warthogs.atlassian.net/browse/DPE-8924) fix scale up from zero when metrics-endpoint is related by @paulomach in [#701](https://github.com/canonical/mysql-k8s-operator/pull/701)
* [DPE-9169](https://warthogs.atlassian.net/browse/DPE-9169) Guard against error when listing roles by @astrojuanlu in [#718](https://github.com/canonical/mysql-k8s-operator/pull/718)

## New contributors

* @Deezzir made their first contribution in [#651](https://github.com/canonical/mysql-k8s-operator/pull/651)
* @astrojuanlu made their first contribution in [#673](https://github.com/canonical/mysql-k8s-operator/pull/673)

**Full Changelog**: https://github.com/canonical/mysql-k8s-operator/compare/rev254...rev342