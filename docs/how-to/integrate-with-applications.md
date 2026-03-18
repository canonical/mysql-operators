---
myst:
  html_meta:
    description: "Integrate Charmed MySQL with charmed applications via mysql_client interface or with non-charmed apps using the data-integrator charm."
---

(integrate-with-applications)=
# How to integrate with applications

[Integrations](https://documentation.ubuntu.com/juju/3.6/reference/relation/) (also *relations*) are connections between two applications with compatible endpoints. These connections simplify the creation and management of users, passwords, and other shared data.

This guide shows how to integrate Charmed MySQL with both charmed and non-charmed applications.

For developer information about how to integrate your own charmed application with MySQL, see {ref}`integrate-with-your-charm`.

## Integrate with a charmed application

Integrations with charmed applications are supported via the [`mysql_client`](https://github.com/canonical/charm-relation-interfaces/blob/main/interfaces/mysql_client/v0/README.md) interface.

### Modern `mysql_client` interface

To integrate with a charmed application that supports the `mysql_client` interface, run

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate mysql <charm>
```

```{tab-item} K8s
:sync: k8s

    juju integrate mysql-k8s <charm>
```
````

To remove the integration, run

````{tab-set}
```{tab-item} VM
:sync: vm

    juju remove-relation mysql <charm>
```

```{tab-item} K8s
:sync: k8s

    juju remove-relation mysql-k8s <charm>
```
````

## Integrate with a non-charmed application

To integrate with an application outside of Juju, you must use the [`data-integrator` charm](https://charmhub.io/data-integrator) to create the required credentials and endpoints.

Deploy `data-integrator`:

```shell
juju deploy data-integrator --config database-name=<name>
```

Integrate with MySQL:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate data-integrator mysql
```

```{tab-item} K8s
:sync: k8s

    juju integrate data-integrator mysql-k8s
```
````

Use the `get-credentials` action to retrieve credentials from `data-integrator`:

```shell
juju run data-integrator/leader get-credentials
```

## Rotate applications password

To rotate the passwords of users created for related applications, the relation should be removed and related again. That process will generate a new user and password for the application.

````{tab-set}
```{tab-item} VM
:sync: vm

    juju remove-relation <charm> mysql
    juju integrate <charm> mysql
```

```{tab-item} K8s
:sync: k8s

    juju remove-relation <charm> mysql-k8s
    juju integrate <charm> mysql-k8s
```
````

### Internal operator user

The operator user is used internally by the Charmed MySQL application. The `set-password` action can be used to rotate its password.

To set a specific password for the `operator` user, run

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader set-password password=<password>
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader set-password password=<password>
```
````

To randomly generate a password for the `operator` user, run

```shell
juju run mysql/leader set-password
```

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader set-password
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader set-password
```
````

```{seealso}
{ref}`manage-passwords`
```