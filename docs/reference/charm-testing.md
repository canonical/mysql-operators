---
myst:
  html_meta:
    description: "Reference overview of software test types for Charmed MySQL, including smoke and integration tests, for charm developers and contributors."
---

(charm-testing)=
# Charm testing

<!--TODO: migrate this to github dev docs-->

This reference describes the different [software test types](https://en.wikipedia.org/wiki/Software_testing) that are applicable to Charmed MySQL. It is intended for charm developers and contributors.

## Smoke test

```{eval-rst}
.. list-table::
   :header-rows: 0

   * - **Complexity**
     - trivial
   * - **Speed**
     - fast
   * - **Goal**
     - ensure basic functionality works over short amount of time
```

Create a Juju model for testing, deploy a database with a test application and start the "continuous write" test:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju add-model smoke-test

    juju deploy mysql --channel 8.4/edge --config profile=testing
    juju add-unit mysql -n 2 # (optional)

    juju deploy mysql-test-app --channel latest/edge
    juju relate mysql-test-app mysql:database

    # Make sure random data inserted into DB by test application:
    juju run mysql-test-app/leader get-inserted-data

    # Start "continuous write" test:
    juju run mysql-test-app/leader start-continuous-writes
    export password=$(juju run mysql/leader get-password username=root | yq '.. | select(. | has("password")).password')
    watch -n1 -x juju ssh mysql/leader "mysql -h 127.0.0.1 -uroot -p${password} -e \"select count(*) from continuous_writes.data\""

    # Watch the counter is growing!
```

```{tab-item} K8s
:sync: k8s

    juju add-model smoke-test

    juju deploy mysql-k8s --trust --channel 8.4/edge --config profile=testing
    juju scale-application mysql-k8s 3 # (optional)

    juju deploy mysql-test-app --channel latest/edge
    juju relate mysql-test-app mysql-k8s:database

    # Make sure random data inserted into DB by test application:
    juju run mysql-test-app/leader get-inserted-data

    # Start "continuous write" test:
    juju run mysql-test-app/leader start-continuous-writes
    export password=$(juju run mysql-k8s/leader get-password username=root | yq '.. | select(. | has("password")).password')
    watch -n1 -x juju ssh --container mysql mysql-k8s/leader "mysql -h 127.0.0.1 -uroot -p${password} -e \"select count(*) from continuous_writes.data\""

    # Watch the counter is growing!
```
````


Expected results:

* mysql-test-app continuously inserts records in database `continuous_writes` table `data`.
* the counters (amount of records in table) are growing on all cluster members

Hints:

```shell
# Stop "continuous write" test
juju run mysql-test-app/leader stop-continuous-writes

# Truncate "continuous write" table (delete all records from DB)
juju run mysql-test-app/leader clear-continuous-writes
```

## Unit tests

<!--TODO: table-->

Please check the [Contributing](https://github.com/canonical/mysql-operators/blob/8.4/edge/CONTRIBUTING.md) guide and follow the `tox` examples there.

## Integration tests

<!--TODO: table-->

Please check the [Contributing](https://github.com/canonical/mysql-operators/blob/8.4/edge/CONTRIBUTING.md) guide and follow the `tox` examples there.

## System test

<!--TODO: table-->

To deploy and test all parts at once, use the MySQL bundle:
* [mysql-bundle](https://charmhub.io/mysql-bundle) for machines
* [mysql-k8s-bundle](https://charmhub.io/mysql-k8s-bundle) for Kubernetes

## Performance test

<!--TODO: table-->

Refer to the [Charmed Sysbench documentation](https://charmhub.io/sysbench).

