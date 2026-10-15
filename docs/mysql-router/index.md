---
myst:
  html_meta:
    description: "Official documentation for the Charmed MySQL Router operator. Deploy and manage MySQL Router on VMs and Kubernetes using Juju."
---

# MySQL Router documentation

The MySQL Router Operator delivers automated operations management from [day 0 to day 2](https://codilime.com/blog/day-0-day-1-day-2-the-software-lifecycle-in-the-cloud-age/) on the [MySQL Router Community Edition](https://www.mysql.com/products/community/) lightweight middleware that provides transparent routing between your application and back-end MySQL Servers. It is an open source, end-to-end, production-ready data platform component on top of [Juju](https://juju.is/).

![image|690x424](upload://vpevillwv3S9C44LDFBxkGCxpGq.png)

MySQL Router is part of InnoDB Cluster, and is lightweight middleware that provides transparent routing between your application and back-end MySQL Servers. It can be used for a wide variety of use cases, such as providing high availability and scalability by effectively routing database traffic to appropriate back-end MySQL Servers. The pluggable architecture also enables developers to extend MySQL Router for custom use cases.

## In this documentation

This documentation contains practical information about installing and operating Charmed MySQL Router. It covers instructions for both VM and K8s substrates.

* **Get started**: {ref}`tutorial` • {ref}`deploy`
* **How-to guides for common operations**: {ref}`enable-tls` • {ref}`integrate` • {ref}`upgrade`
* **Reference**: {ref}`release-notes` • {ref}`system-requirements`
* **Explanations and technical context**: {ref}`legacy-charm` • {ref}`interfaces`

## Project and community

Charmed MySQL Router is an open-source project that welcomes community contributions, suggestions, fixes and constructive feedback.

### Get involved

* [Discourse forum](https://discourse.charmhub.io/tag/mysql)
* [Public Matrix channel](https://matrix.to/#/#charmhub-data-platform:ubuntu.com)
* [Report an issue](https://github.com/canonical/mysql-router-operators/issues/new/choose)
* [Contribute](https://github.com/canonical/mysql-router-operators/blob/8.4/edge/CONTRIBUTING.md)

### Governance and policies

* [Code of Conduct](https://ubuntu.com/community/code-of-conduct)

```{toctree}
:caption: MySQL Router
:hidden:

Tutorial <tutorial>
How-to guides <how-to/index>
Reference <reference/index>
Explanation <explanation/index>
```