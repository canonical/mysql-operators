---
myst:
  html_meta:
    description: "Learn how to retrieve and rotate passwords for Charmed MySQL users using the get-password and set-password Juju actions on the leader unit."
---

(manage-passwords)=
# How to manage passwords

Charmed MySQL user credentials are managed with Juju's `get-password` and `set-password` actions.

```{seealso}
{ref}`users`
```

## Get password

To retrieve user credentials for the `root` user, run the `get-password` action on the leader unit as follows:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader get-password
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader get-password
```
````

To retrieve credentials for a different user:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader get-password username=<username>
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader get-password username=<username>
```
````

## Set password

To change the `root` user's password to a new, randomized password:

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

To set a manual password for the `root` user:

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

To set a manual password for another user:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader set-password username=<username> password=<password>
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader set-password username=<username> password=<password>
```
````

