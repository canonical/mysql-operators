---
myst:
  html_meta:
    description: "Migrate database data from Charmed MySQL 8.0 to Charmed MySQL 8.4."
---

(migrate-data-from-8.0-to-8.4)=
# Migrate data from MySQL 8.0 to 8.4

Charmed MySQL 8.4 introduces breaking changes regarding permissions, operator usernames, and refresh mechanisms.
It is recommended to manually migrate the data from the 8.0 database to the 8.4 database.

There are two possible ways to do so:

```{seealso}
* {ref}`migrate-data-mysqldump`
* {ref}`migrate-data-mysqlsh`
```
