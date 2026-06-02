---
myst:
  html_meta:
    description: "Reference overview of software test types for Charmed MySQL, including smoke and integration tests, for charm developers and contributors."
---

(charm-testing)=
# Charm testing

<!--TODO: migrate this to github dev docs-->

This reference describes the different [software test types](https://en.wikipedia.org/wiki/Software_testing) that are applicable to Charmed MySQL. It is intended for charm developers and contributors.

The following diagram highlights how the main test suites can end in either a successful or failed result, and what each outcome typically demonstrates:

```{mermaid}
flowchart LR
    test_run([Charm test execution]) --> smoke[Smoke tests]
    test_run --> unit[Unit tests]
    test_run --> integration[Integration tests]
    test_run --> system[System tests]
    test_run --> performance[Performance tests]

    smoke --> smoke_ok[Continuous writes keep growing]
    smoke --> smoke_fail[Writes stop or counters diverge]

    unit --> unit_ok[Charm logic behaves as expected]
    unit --> unit_fail[Regression in isolated charm logic]

    integration --> integration_ok[Charm integrates correctly with Juju and related apps]
    integration --> integration_fail[Cross-component workflow breaks]

    system --> system_ok[End-to-end bundle deployment stays healthy]
    system --> system_fail[Full deployment behavior regresses]

    performance --> performance_ok[Throughput and latency stay within target]
    performance --> performance_fail[Performance falls below target]

    classDef success fill:#dff3e4,stroke:#2b8a3e,color:#0b3d20;
    classDef failure fill:#fde2e1,stroke:#c92a2a,color:#5c1a18;

    class smoke_ok,unit_ok,integration_ok,system_ok,performance_ok success;
    class smoke_fail,unit_fail,integration_fail,system_fail,performance_fail failure;
```

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
    juju integrate mysql-test-app mysql:database

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
    juju integrate mysql-test-app mysql-k8s:database

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
