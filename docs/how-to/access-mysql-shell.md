---
myst:
  html_meta:
    description: "Learn how-to get mysql-shell client access on Charmed MySQL units"
---


(access-mysql-shell)=
# Access MySQL Shell on a unit

Charmed MySQL uses [mysql-shell](https://dev.mysql.com/doc/mysql-shell/8.4/en/) as main contact
point between the operator code and MySQL daemon.

For some (rare) cases, is possible for the user to access the mysql-shell client running on the
unit container/virtual-machine.

## Get operator password

The different possible database users depend on the privileges
required. More information can be found in {ref}`users`.

In this guide, we will use the `charmed-operator` user as an example.

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader get-password username=charmed-operator
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader get-password username=charmed-operator
```
````

## Access the shell

With the password now it is possible to log in with:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju ssh mysql/0 sudo charmed-mysql.mysqlsh charmed-operator:<password>@localhost
```

```{tab-item} K8s
:sync: k8s

    juju ssh --container mysql mysql-k8s/0 mysqlsh charmed-operator:<password>@localhost
```
````

Don't forget to replace the `<password>` placeholder with your password.

## Switch between Python and SQL mode

MySQL Shell provides both SQL and Python prompt, with differing set of features.
To switch from Python to SQL in a logged-in prompt, use the `\sql` command.
To switch back to Python, use the `\py` command.

