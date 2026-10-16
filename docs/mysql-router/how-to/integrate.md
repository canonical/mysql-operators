(integrate-router)=
# How to integrate with other applications

## Modern `mysql_client` interface:

Relations to new applications are supported via the [mysql_client](https://github.com/canonical/charm-relation-interfaces/blob/main/interfaces/mysql_client/v0/README.md) interface. It does **not** support the legacy `mysql` interface.

To create a relation with an application that implements the `mysql_client` interface: <!--TODO: might be confusing to say "application" instead of "charm"? -->

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate mysql-router <application>
```
```{tab-item} K8s
:sync: k8s

    juju integrate mysql-router-k8s <application>
```
````

To remove a relation:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju remove-relation mysql-router <application>
```
```{tab-item} K8s
:sync: k8s

    juju remove-relation mysql-router-k8s <application>
```
````

See compatible charms for integration on the MySQL Router Charmhub pages:

* [MySQL Router VM integrations](https://charmhub.io/mysql-router/integrations?channel=8.4/stable)
* [MySQL Router K8s integrations](https://charmhub.io/mysql-router-k8s/integrations?channel=8.4/stable)

## Internal operator user

To rotate the internal router passwords, the relation with backend-database should be removed and related again. That process will generate a new user and password for the application, while retaining the requested database and data.

````{tab-set}
```{tab-item} VM
:sync: vm

    juju remove-relation mysql-router mysql
    juju integrate mysql-router mysql
```
```{tab-item} K8s
:sync: k8s

    juju remove-relation mysql-router-k8s mysql-k8s
    juju integrate mysql-router-k8s mysql-k8s
```
````
