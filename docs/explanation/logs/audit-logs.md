---
myst:
  html_meta:
    description: "Understand how the Audit Log plugin works in Charmed MySQL, including output samples, storage paths, rotation frequency, and configuration options."
---

(audit-logs)=
# Audit logs

The Audit Log plugin allows fine grained configuration for all login/logout, queries or both records to be stored in a log file. It is enabled in Charmed MySQL by default.

## Overview

The following is a sample of the audit logs, in JSON format with only logins records (default configuration):

```json
{"audit_record":{"name":"Quit","record":"6_2024-09-03T01:53:14","timestamp":"2024-09-03T01:53:33Z","connection_id":"992","status":0,"user":"clusteradmin","priv_user":"clusteradmin","os_login":"","proxy_user":"","host":"localhost","ip":"","db":""}}
{"audit_record":{"name":"Connect","record":"7_2024-09-03T01:53:14","timestamp":"2024-09-03T01:53:33Z","connection_id":"993","status":1156,"user":"","priv_user":"","os_login":"","proxy_user":"","host":"juju-da2225-8","ip":"10.207.85.214","db":""}}
{"audit_record":{"name":"Connect","record":"8_2024-09-03T01:53:14","timestamp":"2024-09-03T01:53:33Z","connection_id":"994","status":0,"user":"serverconfig","priv_user":"serverconfig","os_login":"","proxy_user":"","host":"juju-da2225-8","ip":"10.207.85.214","db":""}} 
```

````{tab-set}
```{tab-item} VM
:sync: vm

The logs are stored in the `/var/snap/charmed-mysql/common/var/log/mysql` directory, and are rotated every minute to the `/var/snap/charmed-mysql/common/var/log/mysql/archive_audit` directory.
```

```{tab-item} K8s
:sync: k8s

The logs are stored in the `/var/log/mysql` directory of the mysql container, and it's rotated every minute to the `/var/log/mysql/archive_audit` directory.
```
````

It's recommended to integrate the charm with {ref}`COS <enable-monitoring>`, from where the logs can be easily persisted and queried using Loki and Grafana.

## Configurations

### `plugin-audit-enabled`

The audit plugin is enabled by default in the charm, but it's possible to disable it by setting:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju config mysql plugin-audit-enabled=false
```

```{tab-item} K8s
:sync: k8s

    juju config mysql-k8s plugin-audit-enabled=false
```
````

Valid values are `false` and `true` (default). By setting it to false, existing logs are still kept in the `archive_audit` directory.

### `logs_audit_policy` 

Audit log policy:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju config mysql logs_audit_policy=queries
```

```{tab-item} K8s
:sync: k8s

    juju config mysql-k8s logs_audit_policy=queries
```
````

Valid values are `logins` (default), `queries` and `all`.

### `plugin-audit-strategy`

By default the audit plugin writes logs in asynchronous mode for better performance.

To ensure logs are written to disk on more timely fashion, this configuration can be set to semi-synchronous mode:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju config mysql plugin-audit-strategy=semi-async
```

```{tab-item} K8s
:sync: k8s

    juju config mysql-k8s plugin-audit-strategy=semi-async
```
````

Valid values are `async` (default) and `semi-async`.

