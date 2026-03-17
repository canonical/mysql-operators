---
myst:
  html_meta:
    description: "System requirements for Charmed MySQL: Ubuntu and Kubernetes versions, supported Juju releases, MySQL group replication requirements, and hardware specs."
---

(system-requirements)=
# System requirements

The following are the minimum software and hardware requirements to run Charmed MySQL.

## Software

````{tab-set}
```{tab-item} VM
:sync: vm

* Ubuntu 24.04 LTS (Noble) or later
```

```{tab-item} K8s
:sync: k8s

* Ubuntu 24.04 LTS (Noble) or later
* Kubernetes 1.27+
* Canonical MicroK8s 1.27+
  * snap channel `1.27-strict/stable` and newer
```
````

### Juju

The charm supports several Juju releases from [2.9 LTS](https://documentation.ubuntu.com/juju/3.6/reference/juju/juju-roadmap-and-releases/#juju-2-9) onward. The table below shows which minor versions of each major Juju release are supported by the stable Charmhub releases of MySQL. 

Always check the {ref}`release notes <release-notes>` to find the minimum Juju version for your deployment.

````{tab-set}
```{tab-item} VM
:sync: vm

| Juju major release | Supported minor versions | Compatible charm revisions |Comment |
|:--------|:-----|:-----|:-----|
|         |      |      |      |
```

```{tab-item} K8s
:sync: k8s

| Juju major release | Supported minor versions | Compatible charm revisions |Comment |
|:--------|:-----|:-----|:-----|
|         |      |      |      |
```
````

### MySQL group replication requirements

* In order to integrate with this charm, every table created by the integrated application **must have a primary key**. This is required by the [group replication plugin](https://dev.mysql.com/doc/refman/8.4/en/group-replication-requirements.html) enabled in this charm.
* The count of [Charmed MySQL units](https://dev.mysql.com/doc/refman/8.4/en/group-replication-limitations.html) in a single Juju application is limited to 9. Unit 10+ will start; however, they will not join the cluster but sleep in a hot-swap reserve.

## Hardware

Make sure your machine meets the following requirements:
* 8GB of RAM
* 2 CPU threads
* At least 20GB of available storage

````{tab-set}
```{tab-item} VM
:sync: vm

The charm is based on the [charmed-mysql snap](https://snapcraft.io/charmed-mysql). 

It currently supports:
* `amd64`
* `arm64` (charm revision 312+)
* `s390x` (charm revision 443+)
```

```{tab-item} K8s
:sync: k8s

The charm is based on the [charmed-mysql ROCK OCI](https://github.com/canonical/charmed-mysql-rock), which is recursively based on the [charmed-mysql snap](https://snapcraft.io/charmed-mysql). 

It currently supports:
* `amd64`
* `arm64` (charm revision 181+)
* `s390x` (charm revision 342+)
```
````

{ref}`Contact us <contacts>` if you are interested in a new architecture!

## Networking

* Access to the internet for downloading the required snaps, rocks, and charms.
  * For air-gapped environments, see our `offline deployment guide <air-gapped>`
* Only IPv4 is supported at the moment
  * See more information about this limitation in [this Jira issue](https://warthogs.atlassian.net/browse/DPE-4695)
  * {ref}`Contact us <contacts>` if you are interested in IPv6!

<!-- BADGES -->
[2.9 LTS]: https://img.shields.io/badge/2.9_LTS-%23E95420?label=Juju
[3.1]: https://img.shields.io/badge/3.1-%23E95420?label=Juju
[3.4]: https://img.shields.io/badge/3.4-%23E95420?label=Juju
[3.5]: https://img.shields.io/badge/3.5-%23E95420?label=Juju
[3.6 LTS]: https://img.shields.io/badge/3.6_LTS-%23E95420?label=Juju

<!-- LINKS -->
[240]: release-notes/vm/revision-240.md
[196]: release-notes/vm/revision-196.md
[151]: release-notes/vm/revision-151.md

[153]: release-notes/k8s/revision-153.md
[99]: release-notes/k8s/revision-99.md
[75]: release-notes/k8s/revision-75.md
