---
myst:
  html_meta:
    description: "Learn about cryptographic mechanisms in Charmed MySQL including resource verification, signed commits, and TLS encryption for cluster connections."
---

(cryptography)=
# Cryptography

This document describes the cryptography used by Charmed MySQL.

## Resource checksums

````{tab-set}
```{tab-item} VM
:sync: vm

Charmed MySQL and Charmed MySQL Router operators use pinned revisions of the [Charmed MySQL snap](https://github.com/canonical/charmed-mysql-snap) to provide reproducible and secure environments.

The Charmed MySQL snap packages the MySQL workload along with the necessary dependencies and utilities required for the operators’ lifecycle. For more details, see the snap contents in the [snapcraft.yaml file](https://github.com/canonical/charmed-mysql-snap/blob/8.4/edge/snap/snapcraft.yaml).
```

```{tab-item} K8s
:sync: k8s

Charmed MySQL K8s and Charmed MySQL Router K8s operators use a pinned version of the [Charmed MySQL rock](https://github.com/canonical/charmed-mysql-rock/pkgs/container/charmed-mysql) to provide reproducible and secure environments.

The rock is an OCI image derived from the respective snap. The Charmed MySQL K8s snap packages the MySQL workload along with the necessary dependencies and utilities required for the operators’ lifecycle. For more details, see the snap contents in the [snapcraft.yaml file](https://github.com/canonical/charmed-mysql-snap/blob/8.4/edge/snap/snapcraft.yaml).
```
````

Every artifact bundled into the Charmed MySQL snap is verified against its MD5, SHA256, or SHA512 checksum after download. The installation of certified snap into the rock is ensured by snap primitives that verify their squashfs filesystems images GPG signature. For more information on the snap verification process, refer to the [snapcraft.io documentation](https://snapcraft.io/docs/assertions).

## Sources verification

MySQL and its extra components (mysql-shell, mysqld-exporter, mysqlrouter-exporter, mysql-server-plugins, mysql-pitr-helper, percona-xtrabackup, etc.) are built by Canonical from upstream source codes into PPAs and stored on [Launchpad](https://launchpad.net/ubuntu/+source/mysql-8.4).

Charmed MySQL charms, snap and ROCK are built and released programmatically using release pipelines implemented via GitHub Actions in their respective repositories.

All repositories in GitHub are set up with branch protection rules, requiring:

* new commits to be merged to main branches via pull request with at least 2 approvals from repository maintainers
* new commits to be signed (e.g. using GPG keys)
* developers to sign the [Canonical Contributor License Agreement (CLA)](https://ubuntu.com/legal/contributors)

## Encryption

Charmed MySQL can be used to deploy a secure MySQL cluster that provides encryption-in-transit capabilities out of the box for:

* Cluster communications
* MySQL Router connection
* External client connection

To set up a secure connection Charmed MySQL and Charmed MySQL Router need to be integrated with TLS Certificate Provider charms, e.g. `self-signed-certificates` operator. Certificate Signing Requests (CSRs) are generated for every unit using the `tls_certificates_interface` library that uses the `cryptography` Python library to create X.509 compatible certificates. The CSR is signed by the TLS Certificate Provider, returned to the units, and stored in Juju secret. The relation also provides the CA certificate, which is loaded into Juju secret.

Encryption at rest is currently not supported, although it can be provided by the substrate (cloud or on-premises).

## Authentication

In Charmed MySQL, authentication layers can be enabled for:

1. MySQL Router connections
2. MySQL cluster communication
3. MySQL clients connections

### MySQL Router authentication to MySQL

Authentication to MySQL Router is based on the [caching_sha2_password auth plugin](https://dev.mysql.com/doc/refman/8.4/en/caching-sha2-pluggable-authentication.html).

Credentials are exchanged via [Juju secrets](https://canonical-juju.readthedocs-hosted.com/en/latest/user/howto/manage-secrets/).

### MySQL cluster authentication

Authentication among members of a MySQL cluster is based on the [caching_sha2_password auth plugin](https://dev.mysql.com/doc/refman/8.4/en/caching-sha2-pluggable-authentication.html).

An internal user is used for this authentication with its hashed password stored in a system metadata database.

### Client authentication to MySQL

Authentication to MySQL Router is based on the [caching_sha2_password auth plugin](https://dev.mysql.com/doc/refman/8.4/en/caching-sha2-pluggable-authentication.html).

Credentials are exchanged via [Juju secrets](https://canonical-juju.readthedocs-hosted.com/en/latest/user/howto/manage-secrets/).

