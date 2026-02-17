(revision-151)=
# Revision 151

A new revision of Charmed MySQL has been published in the `8.0/stable` channel on [Charmhub](https://charmhub.io/mysql?channel=8.0/stable).

See also: {ref}`System requirements <system-requirements>`, {ref}`How to upgrade <refresh>`

| Architecture | Charm revision  | MySQL version | Minimum Juju version | 
| ------------ | --------------- |-------------- |----------------------|
|   `amd64`    | 151             |  8.0.32       |        2.9.32+       |

## Features

* Deploy on VM (tested with LXD, MAAS)
  * juju constraints are supported to limit CPU/RAM/Storage size
* Scaling up/down in one simple juju command
* HA using [Innodb Group replication](https://dev.mysql.com/doc/refman/8.0/en/group-replication.html)
* Full backups and restores are supported when using any S3-compatible storage
* TLS support (using “[tls-certificates](https://charmhub.io/tls-certificates-operator)” operator)
* DB access outside of Juju using “[data-integrator](https://charmhub.io/data-integrator)”
* Data import using standard tools e.g. mysqldump, etc.
* Documentation:

|Charm|Version|Charm channel|Documentation|License|
| --- | --- | --- | --- | --- |
|[MySQL](https://github.com/canonical/mysql-operator)|8.0.32|[8.0/stable](https://charmhub.io/mysql) (r151)|[Tutorial](https://charmhub.io/mysql/docs/t-overview?channel=8.0/edge), [README](https://github.com/canonical/mysql-operator/blob/main/README.md), [Contributing](https://github.com/canonical/mysql-operators/blob/main/CONTRIBUTING.md)|[Apache 2.0](https://github.com/canonical/mysql-operator/blob/main/LICENSE)|

**Full Changelog**: https://github.com/canonical/mysql-operator/commits/rev151

## What is inside the charms

* Charmed MySQL charm ships the latest MySQL “8.0.32-0ubuntu0.22.04.2”
* VM charms [based on our](https://snapcraft.io/publisher/dataplatformbot) SNAP (Ubuntu LTS “22.04” - core22-based)
* Principal charms supports the latest LTS series “22.04” only.
* Subordinate charms support LTS “22.04” and “20.04” only.

## Technical notes

Compatibility with legacy charms:
  * New MySQL charm is a juju-interface compatible replacement for legacy charms such as “[MariaDB](https://charmhub.io/mariadb)”, “[OSM MariaDB](https://charmhub.io/charmed-osm-mariadb-k8s)”, “[Percona Cluster](https://charmhub.io/percona-cluster)” and “[Mysql Innodb Cluster](https://charmhub.io/mysql-innodb-cluster)” (using legacy interface “mysql”, via endpoints “mysql” and “mysql-root”). Other legacy interfaces such as “[mysql-router](https://github.com/canonical/mysql-operator/#mysql-router-interface-db-router-endpoint)” interface (“db-router” endpoint) and “[mysql-shared](https://github.com/canonical/mysql-operator/#mysql-router-interface-db-router-endpoint)” interface (“shared-db” endpoint) are also supported. However, it is highly recommended to migrate to the modern interface ‘[mysql_client ](https://github.com/canonical/charm-relation-interfaces)’. It can be easily done using the charms library ‘[data_interfaces](https://charmhub.io/data-platform-libs/libraries/data_interfaces)’ from ‘[data-platform-libs](https://github.com/canonical/data-platform-libs/)’.

Please contact us, see details below, if you are considering migrating from other “legacy” charms not mentioned above. Additionally:
* Tracks description:
  * Charm MySQL charm follows the SNAP track “8.0”.
* No “latest” track in use (no surprises in tracking “latest/stable”)!
  * Charmed MySQL charms provide the {ref}`legacy charm <legacy-charm>` through “latest/stable”.
* Charm lifecycle flowchart diagrams: [MySQL](https://github.com/canonical/mysql-k8s-operator/tree/main/docs/reference).
* Modern interfaces are well described in “[Interfaces catalogue](https://github.com/canonical/charm-relation-interfaces)” and implemented by '[data-platform-libs](https://github.com/canonical/data-platform-libs/)'.

## How to reach us

Consider [opening a GitHub issue](https://github.com/canonical/mysql-operator/issues) if you want to open a bug report. 

For more details, see {ref}`contacts`.

---

This document was originally posted [here](https://discourse.charmhub.io/t/juju-operators-for-postgresql-and-mysql-are-now-stable/10223).