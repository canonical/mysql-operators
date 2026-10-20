(scale-router)=
# How to scale units

To deploy MySQL Router with multiple units, use the `-n` option:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql-router --channel dpe/candidate -n <number of units>
```
```{tab-item} K8s
:sync: k8s

    juju deploy mysql-router-k8s --channel 8.0/stable -n <number of units> --trust
```
````

## Scale an existing deployment

````{tab-set}
```{tab-item} VM
:sync: vm

MySQL Router is a subordinated charm, both scaling-up and scaling-down operations are performed via principal application using `juju add-unit`:

    juju add-unit application -n <desired_num_of_units>

The subordinated application will be scaled automatically, following the principal application.
```
```{tab-item} K8s
:sync: k8s

Both scaling-up and scaling-down operations are performed using `juju scale-application`:

    juju scale-application mysql-router-k8s <desired_num_of_units>
```
````
