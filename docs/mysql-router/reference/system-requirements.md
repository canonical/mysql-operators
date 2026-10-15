(system-requirements-router)=
# System requirements

The following are the minimum software and hardware requirements to run Charmed MySQL Router alongside Charmed MySQL 8.4.

## Software

````{tab-set}
```{tab-item} VM
:sync: vm

* Ubuntu 26.04 LTS (Resolute) or later
* Juju 3.6 or later
```

```{tab-item} K8s
:sync: k8s

* Ubuntu 26.04 LTS (Resolute) or later
* Kubernetes 1.27+
* Canonical MicroK8s 1.27+
  * snap channel `1.27-strict/stable` and later
* Juju 3.6 or later
```
````

<!--TODO: mysql requires k8s 1.34+. Update?-->

## Hardware

Make sure your machine meets the following requirements:

* 8GB of RAM
* 2 CPU threads
* At least 20GB of available storage
* Access to the internet for downloading the required OCI/ROCKs and charms.

````{tab-set}
```{tab-item} VM
:sync: vm

The charm is based on the [charmed-mysql snap](https://snapcraft.io/charmed-mysql).

It currently supports:
* `amd64`
* `arm64`
* `s390x`
```
```{tab-item} K8s
:sync: k8s

The charm is based on the [charmed-mysql ROCK OCI](https://github.com/canonical/charmed-mysql-rock), which is recursively based on the [charmed-mysql snap](https://snapcraft.io/charmed-mysql).

It currently supports:
* `amd64`
* `arm64`
* `s390x`
```
````

{ref}`Contact us <contacts>` if you are interested in a new architecture!
