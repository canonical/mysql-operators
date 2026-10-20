(interfaces-router)=
# Charm interfaces and endpoints

MySQL Router supports modern ['mysql_client'](https://github.com/canonical/charm-relation-interfaces) interface. Applications can easily connect MySQL using ['data_interfaces'](https://charmhub.io/data-platform-libs/libraries/data_interfaces) library from ['data-platform-libs'](https://github.com/canonical/data-platform-libs/).

```{attention}
In order to relate with Charmed MySQL, **every table created by the client application must have a primary key.**

This is required by the [group replication plugin](https://dev.mysql.com/doc/refman/8.0/en/group-replication-requirements.html) enabled in this charm.
```

## Modern `mysql_client` interface (`database` endpoint):

Adding a relation is accomplished with `juju integrate` via endpoint `database`.

Example:

````{tab-set}
```{tab-item} VM
:sync: vm

    # Deploy Charmed MySQL and MySQL Router clusters
    juju deploy mysql -n 3
    juju deploy mysql-router -n 3 --channel dpe/candidate
    
    # Deploy the relevant charms, e.g. mysql-test-app
    juju deploy mysql-test-app
    
    # Relate all applications
    juju integrate mysql mysql-router
    juju integrate mysql-router:database mysql-test-app
    
    # Check established relation (using mysql_client interface):
    juju status --relations
    
    # Example of the properly established relation:
    # > Integration provider        Requirer                         Interface           Type     Message
    # > mysql:database              mysql-router:backend-database    mysql_client        regular
    # > mysql-router:database       mysql-test-app:database          mysql_client        regular         
    # > ...

See all the charm interfaces on the [MySQL Router VM Charmhub page](https://charmhub.io/mysql-router/integrations?channel=dpe/candidate).
```
```{tab-item} K8s
:sync: k8s

    # Deploy Charmed MySQL K8s and MySQL Router K8s clusters with 3 nodes each
    juju deploy mysql-k8s -n 3 --trust
    juju deploy mysql-router-k8s -n 3 --trust --channel 8.0/stable
    
    # Deploy the relevant charms, e.g. mysql-test-app
    juju deploy mysql-test-app
    
    # Relate all applications
    juju integrate mysql-k8s mysql-router-k8s
    juju integrate mysql-router-k8s:database mysql-test-app
    
    # Check established relation (using mysql_client interface):
    juju status --relations
    
    # Example of the properly established relation:
    # > Integration provider                 Requirer                             Interface           Type     Message
    # > mysql-k8s:database                   mysql-router-k8s:backend-database    mysql_client        regular
    # > mysql-router-k8s:database            mysql-test-app:database              mysql_client        regular         
    # > ...

See all the charm interfaces on the [MySQL Router K8s Charmhub page](https://charmhub.io/mysql-router-k8s/integrations?channel=8.0/stable).
```
````
