---
myst:
  html_meta:
    description: "Understand how Juju orchestrates Charmed MySQL and learn about command differences between Juju 2.9 and Juju 3.x relevant to this documentation."
---

(juju)=
# Juju 

[Juju](https://juju.is/) is an open source orchestration engine for software operators that enables the deployment, integration and lifecycle management of applications at any scale, on any infrastructure using charms.

This charm is an operator - business logic encapsulated in reusable software packages that automate every aspect of an application's life. Charms are shared via [CharmHub](https://charmhub.io/).

See also:

* [Juju Documentation](https://juju.is/docs/juju) and [Blog](https://ubuntu.com/blog/tag/juju)
* [Charm SDK](https://juju.is/docs/sdk)

This page aims to provide some context on some of the inner workings of Juju that affect this charm.

(breaking-changes-juju)=
## Breaking changes between Juju 2.9 and 3

As this charm documentation is written for Juju 3.x, users of 2.9.x will encounter noteworthy changes when following the instructions. This section explains those changes.

Breaking changes have been introduced in the Juju client between versions 2.9.x and 3.x. These are caused by the renaming and re-purposing of several commands - functionality and command options remain unchanged.

In the context of this guide, the pertinent changes are shown here:

|2.9.x|3.x|
| --- | --- |
|`add-relation`|`integrate`|
|`relate`|`integrate`|
|`run`|`exec`|
|`run-action --wait`|`run`|

See the [Juju 3.0 release notes](https://documentation.ubuntu.com/juju/3.6/reference/juju/juju-roadmap-and-releases/#juju-3-0-0-22-oct-2022) for the comprehensive list of changes.

The response is to therefore substitute the documented command with the equivalent 2.9.x command. For example:

### Juju 3.x:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate mysql:database mysql-test-app

    juju run mysql/leader get-password 
```

```{tab-item} K8s
:sync: k8s

    juju integrate mysql-k8s:database mysql-test-app

    juju run mysql-k8s/leader get-password 
```
````

### Juju 2.9.x:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju relate mysql:database mysql-test-app

    juju run-action --wait mysql/leader get-password
```

```{tab-item} K8s
:sync: k8s

    juju relate mysql-k8s:database mysql-test-app

    juju run-action --wait mysql-k8s/leader get-password
```
````

```{note}
This section is based on the [OpenStack guide.](https://docs.openstack.org/charm-guide/latest/project/support-notes.html#breaking-changes-between-juju-2-9-x-and-3-x)
```

(explanation-juju-upgrades)=
## Juju  upgrades

Newly released charm revisions might require a new Juju version. This is usually because the new revision requires new Juju features, e.g. [Juju secrets](https://juju.is/docs/juju/secret).

Information about Juju requirements will be clearly indicated in the charm's {ref}`release notes <release-notes>` and in the repository's `metadata.yaml` file.

When upgrading your database charm with {command}`juju refresh` Juju checks that its version is compatible with the target revision. If not, it stops the upgrade and prevents further changes to keep the installation safe. 

```shell
~$ juju refresh mysql

Added charm-hub charm "mysql", revision XX in channel 8.4/stable, to the model
ERROR Charm feature requirements cannot be met:
    - charm requires all of the following:
      - charm requires feature "juju" (version >= 3.6.0) but model currently supports version 3.5.0
```

You must then {ref}`upgrade to the required Juju version <upgrade-juju>` before proceeding with the charm upgrade.

