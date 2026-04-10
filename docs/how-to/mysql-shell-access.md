---
myst:
  html_meta:
    description: "Learn how-to get mysql-shell client access on Charmed MySQL units"
---


(mysql-shell-access)=
# MySQL shell access on units

Charmed MySQL uses mysql-shell as main contact point between the operator code and MySQL daemon.
For some (rare) cases, is possible for the user to access the mysql-shell client running on the
unit container/virtual-machine.

## Get operator password

There are a couple of possible database users that might be used, depending on the privileges
required. More information can be found at the {ref}`Users documentation <users>`.

For this how-to we will use the `serverconfig` user.

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader get-password username=serverconfig
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader get-password username=serverconfig
```
````

## Access the shell

With the password now it's possible to log-in with:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju ssh mysql/0 sudo charmed-mysql.mysqlsh serverconfig:<password>@localhost
```

```{tab-item} K8s
:sync: k8s

    juju ssh --container mysql mysql-k8s/0 mysqlsh serverconfig:<password>@localhost
```
````

Don't forget to replace the password on the `<password>` placeholder.
