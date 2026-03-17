---
myst:
  html_meta:
    description: "Migrate database data to Charmed MySQL using Percona XtraBackup and S3 storage, applicable to legacy charm migrations and external MySQL imports."
---

(migrate-data-backup-restore)=
# How to migrate data via backup/restore

Charmed MySQL is able to {ref}`restore <restore-a-backup>` backups stored on S3-compatible storage. 

The same restore approach is applicable to restore {ref}`external backups <migrate-a-cluster>` made by a different Charmed MySQL installation, or even another MySQL charm. (Note that, in this case, the backup must be created manually using Percona XtraBackup)

Note that, in this case, the backup must be created manually using Percona XtraBackup.

## Prepare

Before migrating data, verify the {ref}`system-requirements`

## Migrate via backup/restore

The approach described below is a general recommendation, but we **cannot guarantee restoration results**. {ref}`Contact us <contacts>` if you have any doubts about data migration/restoration.

And, as always, try it out in a test environment before migrating in production!

* Retrieve root/admin level credentials from legacy charm.
  * Example: {ref}`mysqldump-obtain-legacy-credentials`
* Install [Percona XtraBackup](https://www.percona.com/software/mysql-database/percona-xtrabackup) inside the old charm OR remotely.
  * Ensure the version is compatible with xtrabackup in `Charmed MySQL` revision you are going to deploy. See [installation examples](https://docs.percona.com/percona-xtrabackup/8.4/installation.html).
  * You can also use the [`charmed-mysql` snap](https://snapcraft.io/charmed-mysql) or [rock](https://github.com/canonical/charmed-mysql-rock) directly. For more details, see {ref}`architecture`.
* Configure storage for database backup
  * S3-based is recommended. See {ref}`configure-s3-aws`
* Create a first full logical backup during the off-peak
  * [Example of backup command](https://github.com/canonical/mysql-operator/blob/main/lib/charms/mysql/v0/mysql.py#L2160-L2185).  <!--TODO: probably incorrect, better to hardcode example in docs -->
* Restore the external backup to a Charmed MySQL installation in a test environment
  * See {ref}`migrate-a-cluster
* Test your application to make sure it accepted the new database
* Schedule and perform the final production migration

Do you have questions? {ref}`Contact us <contacts>` if you are interested in such a data migration!

