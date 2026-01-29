# System requirements

The following are the minimum software and hardware requirements to run Charmed MySQL on Kubernetes.

## Software
* Ubuntu 24.04 (Noble) or later
* Kubernetes 1.27+
* Canonical MicroK8s 1.27+ (snap channel 1.27-strict/stable and newer)

### Juju

The table below shows which minor versions of each major Juju release are supported by the stable Charmhub releases of MySQL K8s. 

| Juju major release | Supported minor versions | Compatible charm revisions | Comment                                                                                                                                   |
|:-------------------|:-------------------------|:---------------------------|:------------------------------------------------------------------------------------------------------------------------------------------|

### MySQL Group Replication requirements

* In order to integrate with this charm, every table created by the integrated application **must have a primary key**. This is required by the [group replication plugin](https://dev.mysql.com/doc/refman/8.4/en/group-replication-requirements.html) enabled in this charm.
* The count of [Charmed MySQL K8s units](https://dev.mysql.com/doc/refman/8.4/en/group-replication-limitations.html) in a single Juju application is limited to 9. Unit 10+ will start; however, they will not join the cluster but sleep in a hot-swap reserve.

## Hardware

Make sure your machine meets the following requirements:
- 8GB of RAM.
- 2 CPU threads.
- At least 20GB of available storage.

The charm is based on the [charmed-mysql ROCK OCI](https://github.com/canonical/charmed-mysql-rock), which is recursively based on the [charmed-mysql snap](https://snapcraft.io/charmed-mysql). It currently supports:
* `amd64`
* `arm64`
* `s390x`

[Contact us](/reference/contacts) if you are interested in a new architecture!

## Networking
* Access to the internet for downloading the required OCI/ROCKs and charms.
* Only IPv4 is supported at the moment
  * See more information about this limitation in [this Jira issue](https://warthogs.atlassian.net/browse/DPE-4695)
  * [Contact us](/reference/contacts) if you are interested in IPv6!
