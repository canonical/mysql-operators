---
relatedlinks: "[Charmhub&#32;|&#32;MySQL&#32;VM](https://charmhub.io/mysql?channel=8.0/stable), [Charmhub&#32;|&#32;MySQL&#32;K8s](https://charmhub.io/mysql-k8s?channel=8.0/stable)"
myst:
  html_meta:
    description: "Official documentation for Charmed MySQL operator. Deploy and manage MySQL Community Edition on VMs and Kubernetes using Juju."
---

# Charmed MySQL documentation

Charmed MySQL is an open-source software operator that deploys and operates [MySQL Community Edition](https://www.mysql.com/products/community/) relational databases on machines or Kubernetes with [Juju](https://juju.is/). 

This operator is built with the latest [Ops framework](https://documentation.ubuntu.com/ops/latest/) and replaces the legacy [MariaDB](https://charmhub.io/mariadb), [OSM MariaDB](https://charmhub.io/charmed-osm-mariadb-k8s), [Percona cluster](https://charmhub.io/percona-cluster) and [MySQL InnoDB cluster](https://charmhub.io/mysql-innodb-cluster) operators.

Charmed MySQL includes features such as cluster-to-cluster replication, TLS encryption, password rotation, backups, and easy integration with other applications both inside and outside of Juju. It meets the need of deploying MySQL in a structured and consistent manner while allowing the user flexibility in configuration, simplifying reliable management of MySQL in production environments.

## In this documentation

This documentation contains practical information about installing and operate Charmed MySQL. It covers instructions for both VM and K8s substrates.  

### Get started

Learn about what's in the charm, how to set up your environment, and perform the most common operations.

* **Charm overview**: {ref}`architecture` • {ref}`system-requirements` • {ref}`release-notes`
* **Deploy MySQL**: {ref}`Guided tutorial <tutorial>` • {ref}`Quickstart <deploy>`
* **Key operations**: {ref}`Scale your cluster <scale-replicas>` • {ref}`Manage user credentials <manage-passwords>` • {ref}`Create a backup <create-a-backup>`

### Production deployments

Advanced deployments and operations focused on production scenarios and high availability.

* **Advanced deployments**: {ref}`Terraform <terraform>` • {ref}`Airgapped <airgapped>` • {ref}`Multiple availability zones <multi-az>` • {ref}`Cluster-cluster replication <cluster-cluster-replication>` 
* **Networking**: {ref}`Juju spaces <juju-spaces>` • {ref}`TLS encryption <enable-tls>` • {ref}`External network access <external-network-access>`
* **Upgrades and data migration**: {ref}`In-place upgrades <refresh>` • {ref}`Cluster and data migration <migrate-data-backup-restore>`
* **Troubleshooting**: {ref}`Overview and tools <troubleshooting>` • {ref}`known-scenarios` • {ref}`Logs <logs>` 

### Charm developers

Information for making your application compatible with MySQL.

* **Charm integrations**: {ref}`Interfaces and endpoints <interfaces-and-endpoints>` • {ref}`How to integrate with MySQL <integrate-with-applications>`
* **Learn more about the MySQL charm's design**: {ref}`Internal users <users>` • {ref}`Roles <roles>` • {ref}`architecture`

## How this documentation is organised

This documentation uses the [Diátaxis documentation structure](https://diataxis.fr/):

* The {ref}`tutorial` provides step-by-step guidance for a beginner through the basics of a deployment in a local machine.
* {ref}`how-to` are more focused, and assume you already have basic familiarity with the product.
* {ref}`reference` contains structured information for quick lookup, such as system requirements and configuration parameters
* {ref}`explanation` gives more background and context about key topics

## Project and community

Charmed MySQL is an open-source project that welcomes community contributions, suggestions, fixes and constructive feedback.

### Get involved

* [Discourse forum](https://discourse.charmhub.io/tag/mysql)
* [Public Matrix channel](https://matrix.to/#/#charmhub-data-platform:ubuntu.com)
* [Report an issue](https://github.com/canonical/mysql-operators/issues/new/choose)
* [Contribute](https://github.com/canonical/mysql-operators/blob/main/CONTRIBUTING.md)

### Governance and policies

* [Code of Conduct](https://ubuntu.com/community/code-of-conduct)


```{toctree}
:titlesonly:
:maxdepth: 2
:hidden:

Home <self>
tutorial
How-to guides <how-to/index>
Reference <reference/index>
Explanation <explanation/index>
```
