---
myst:
  html_meta:
    description: "Reference for Charmed MySQL resource profiles (production and testing), their configuration parameters, and how to set or change them with juju config."
---

(profiles)=
# Profiles

Charmed MySQL's usage of resources depends on the chosen profile:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql --config profile=<profile>
```

```{tab-item} K8s
:sync: k8s

    juju deploy mysql-k8s --trust --config profile=<profile>
```
````

## Profile values

<!--TODO: check/update these values and links -->

| Value | Description | Details |
| --- | --- | ----- |
|`production`<br>(default)|[Maximum performance]| ~75% of [unit] memory granted for MySQL<br/>`max_connections`= [RAM / 12MiB] (max safe value)|
|`testing`|[Minimal resource usage]| `innodb_buffer_pool_size` = 20MB<br/> `innodb_buffer_pool_chunk_size`=1MB<br/> `group_replication_message_cache_size`=128MB<br/>`max_connections`=100<br/> `performance-schema-instrument`='memory/%=OFF' |

You can also see all MySQL charm configuration options on Charmhub ([VM](https://charmhub.io/mysql/configure#profile) | [K8s](https://charmhub.io/mysql-k8s/configure#profile)).

## Change profile

<!--TODO: check if this ticket is done.
**Note**: Pre-deployed application profile change is [planned](https://warthogs.atlassian.net/browse/DPE-2404) but currently is NOT supported. -->

To change the profile, use the [`juju config` command](https://documentation.ubuntu.com/juju/3.6/reference/juju-cli/list-of-juju-cli-commands/config/). For example:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql --config profile=testing && \
    juju config mysql profile=production
```

```{tab-item} K8s
:sync: k8s

    juju deploy mysql-k8s --trust --config profile=testing && \
    juju config mysql-k8s profile=production
```
````

## Juju constraints

[Juju constraints](https://juju.is/docs/juju/constraint) allows setting RAM/CPU limits for [units](https://juju.is/docs/juju/unit):


````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql --constraints cores=8 mem=16G
```

```{tab-item} K8s
:sync: k8s

    juju deploy mysql-k8s --trust --constraints cores=8 mem=16G
```
````

Juju constraints can be set together with the charm profile:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql --constraints cores=8 mem=16G --config profile=testing
```

```{tab-item} K8s
:sync: k8s

    juju deploy mysql-k8s --trust --constraints cores=8 mem=16G --config profile=testing
```
````


<!-- Links -->

[Maximum performance]: https://github.com/canonical/mysql-operator/blob/main/lib/charms/mysql/v0/mysql.py#L766-L775

[unit]: https://juju.is/docs/juju/unit

[RAM / 12MiB]: https://github.com/canonical/mysql-operator/blob/53e54745f47b6d2184c54386ee984792cb939152/lib/charms/mysql/v0/mysql.py#L2092

[Minimal resource usage]: https://github.com/canonical/mysql-operator/blob/main/lib/charms/mysql/v0/mysql.py#L759-L764
