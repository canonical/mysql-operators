# `juju status --format json`: real shape and parsing traps

Verified on juju 3.6.29, k8s (caas) model. Machine models have the same
nesting with extra `machines`/`containers` content.

## Top-level keys

```
model          — name, type, controller, cloud, version, model-status, sla
machines       — machine models only; k8s models: usually {}
applications   — map keyed by application name
storage        — {storage: {...}, filesystems: {...}, volumes: {...}}
controller     — {timestamp}
```

## Where the units actually live

`units` is NOT a top-level key. It is nested per application:

```
applications.<app>.units.<app>/<N>
```

A trimmed but faithful example (one-unit mysql-k8s, active/Primary):

```json
{
  "applications": {
    "mysql-k8s": {
      "charm": "mysql-k8s",
      "charm-rev": 423,
      "charm-channel": "8.0/stable",
      "scale": 1,
      "application-status": {"current": "active", "since": "..."},
      "relations": {
        "database-peers": [{"related-application": "mysql-k8s",
                            "interface": "mysql_peers", "scope": "global"}],
        "restart": [{"related-application": "mysql-k8s",
                     "interface": "rolling_op", "scope": "global"}],
        "upgrade": [{"related-application": "mysql-k8s",
                     "interface": "upgrade", "scope": "global"}]
      },
      "units": {
        "mysql-k8s/0": {
          "workload-status": {"current": "active", "message": "Primary"},
          "juju-status": {"current": "idle", "version": "3.6.29"},
          "leader": true,
          "address": "10.1.0.73"
        }
      }
    }
  }
}
```

## Parsing traps (all observed in practice)

- **`units` is nested.** `d["units"]["mysql-k8s/0"]` raises KeyError —
  use `d["applications"][app]["units"]`.
- **Scoping does not flatten.** `juju status mysql-k8s/0 --format json`
  keeps the same nesting (units still under `applications.<app>`).
- **Peer relations appear as self-relations**: `database-peers`,
  `restart`, `upgrade` all list `related-application` = the same app.
  This is how you confirm a peer relation exists and its interface name.
- **Workload status vs agent status** are different keys on the unit:
  `workload-status.current` (charm-set: active/blocked/...) vs
  `juju-status.current` (hook agent: idle/executing/...). Healthy and
  settled = workload `active` AND agent `idle`.
- **`workload-status.message`** is free text from the last hook ("Primary"),
  not structured data.
- **`storage`**: volumes/filesystems nest under `storage.storage["db/0"]`
  (the storage *id*) and cross-reference `volumes`/`filesystems` by
  provider-id. `persistent: false` means the PVC dies with the unit —
  relevant before any destroy or scale-down decision.
- **Model resolution**: a bare `-m <model>` name is ambiguous across
  controllers; use `-m <controller>:<model>` when scripting. But note
  `juju destroy-model` takes `<controller>:<model>` **positionally** —
  it rejects `-m` ("ERROR option provided but not defined: -m").
