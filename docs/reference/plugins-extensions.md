---
myst:
  html_meta:
    description: "Complete reference listing all plugins and extensions supported by Charmed MySQL, with the charm revision that introduced each one for VM and K8s."
---

(plugins-extensions)=
# Supported plugins/extensions

The following list contains all plugins/extensions supported by Charmed MySQL in alphabetical order. The **revision** column indicates which charm revision introduced support for the extension.

If you need support for other extensions, feel free to {ref}`contact us <contacts>`.

````{tab-set}
```{tab-item} VM
:sync: vm

| Plugin/extension name          | Revision                                                                     |
|--------------------------------|------------------------------------------------------------------------------|
| [plugin-audit-enabled](/explanation/logs/audit-logs)         | [272+](https://github.com/canonical/mysql-operator/releases/tag/rev273) |

```

```{tab-item} K8s
:sync: k8s

| Plugin/extension name          | Revision                                                                     |
|--------------------------------|------------------------------------------------------------------------------|
| [plugin-audit-enabled](/explanation/logs/audit-logs)         | [178+](https://github.com/canonical/mysql-k8s-operator/releases/tag/rev179) |

```
````



