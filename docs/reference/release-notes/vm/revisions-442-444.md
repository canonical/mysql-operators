(revisions-442-444)=
# Revisions 442, 443, 444

A new revision of Charmed MySQL has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 444             |  8.0.44       |        3.4.3+        |
|   `arm64`    | 442             |  8.0.44       |        3.4.3+        |
|   `s390x`    | 443             |  8.0.44       |        3.4.3+        |

If you are jumping over several stable revisions, make sure to check {ref}`previous release notes <release-notes-vm>` before upgrading to this revision.

## Highlights

- **Upgraded MySQL to 8.0.44** by @astrojuanlu in [#728](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/728)
- **Added point-in-time backup recovery** by @shayancanonical in [#621](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/621)
- **Added Juju network spaces support** by @sinclert-canonical in [#643](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/643)
- **Introduced stable release on IBM s390x architecture**  by @carlcsaposs-canonical in [#658](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/658)

## Other features

* [DPE-3830] Paxos single leader by @paulomach in [#416](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/416)
* [DPE-7412] Spaces support by @sinclert-canonical in [#643](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/643)
* [DPE-7404] manual primary switchover by @paulomach in [#642](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/642)
* [DPE-7322] Support predefined roles by @sinclert-canonical in [#652](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/652)
* [DPE-8050] Backup action cluster checks by @sinclert-canonical in [#679](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/679)
* [DPE-7322] Tweak database DBA role naming by @sinclert-canonical in [#684](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/684)
* [DPE-8291] Extend Terraform deployment docs by @sinclert-canonical in [#695](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/695)
* [DPE-7242] Add multi-cluster refresh docs by @a-velasco in [#690](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/690)
* [DPE-9006] Allow more connection errors before blocking host by @paulomach in [#732](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/732)

## Bug fixes

* fix: ensure reconfiguration done after leader election by @paulomach in [#635](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/635)
* Bump `httpcore` to version 1.0.9 by @sinclert-canonical in [#640](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/640)
* Migrate release GHA workflow name by @sinclert-canonical in [#644](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/644)
* [DPE-7648] Fix access to not populated instance label by @sinclert-canonical in [#650](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/650)
* [MISC] Fix Juju Spaces lack of addresses by @sinclert-canonical in [#655](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/655)
* [MISC] Fix Juju Spaces lack of addresses (II) by @sinclert-canonical in [#657](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/657)
* fix: [DPE-7404] quorum loss recovery and test fixes by @paulomach in [#671](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/671)
* Fix alert rules screenshot by @a-velasco in [#683](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/683)
* [MISC] Bump Jubilant-backports to v1.4.0 by @sinclert-canonical in [#692](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/692)
* [MISC] Data-replication Jubilant test fixes by @sinclert-canonical in [#697](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/697)
* DPE-7649 Replace `event.set_results(success=False)` with `event.fail()` in action get-cluster-status (take 3) by @astrojuanlu in [#700](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/700)
* [MISC] Replace charmcraft-test by spread by @sinclert-canonical in [#710](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/710)
* [MISC] Downgrade ARM runner to 22.04 by @sinclert-canonical in [#719](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/719)
* [DPE-8600] Point certificates charm to 1/stable by @sinclert-canonical in [#718](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/718)
* [MISC] Fix allure-report publication by @sinclert-canonical in [#721](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/721)
* Fix incompatible downgrade after snapd update by @paulomach in [#723](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/723)
* [DPE-8815] Don't reboot on storage not yet attached by @paulomach in [#716](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/716)
* fix: escape role_name on creation by @paulomach in [#720](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/720)

## New contributors

* @Deezzir made their first contribution in [#680](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/680)
* @astrojuanlu made their first contribution in [#700](https://canonical-charmed-mysql.readthedocs-hosted.com/reference/releases/700)

**Full Changelog**: https://github.com/canonical/mysql-operator/compare/rev366...rev442