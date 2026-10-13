# Using Multiple Juju Controllers Simultaneously

**Question:** Can I use two local Juju controllers (`jujuc-vm-36-27`, a machines controller, and `jujuc-ck8s-36-27`, a Canonical Kubernetes controller) at the same time?

**Answer:** Yes. You do not have to "select" one and lose access to the other. Multiple controllers coexist in the same Juju client (`~/.local/share/juju/controllers.yaml`), and `juju controllers` lists all of them with `*` marking the active one.

## The mechanism — per-command targeting

Only one controller is the "current/active" default, but any command can target a different controller without switching the default:

- `juju <cmd> -c jujuc-ck8s-36-27 …` — runs against the K8s controller while `jujuc-vm-36-27` stays active.
- `juju <cmd> -m jujuc-ck8s-36-27:<model> …` — the `-m` flag accepts `[<controller>:]<model>`.
- The `controller:model` colon syntax also works for `juju switch` (`juju switch jujuc-ck8s-36-27:mymodel`).
- `juju switch -` returns to the previously-selected controller/model.

### Selection precedence

Per the [`juju` environment variables](https://documentation.ubuntu.com/juju/latest/reference/juju-cli/juju-environment-variables/) reference:

> **CLI flag (`-c`/`-m`) > `JUJU_CONTROLLER`/`JUJU_MODEL` env vars > persisted current selection in `controllers.yaml` (under `JUJU_DATA`)**

- `JUJU_CONTROLLER` — "Used to specify the current Juju controller to use. This is overridden if the controller is specified on the command line using `-c CONTROLLER`."
- `JUJU_MODEL` — "Used to specify the current Juju model to use. This is overridden if the model is specified on the command line using `-m MODEL`."
- `JUJU_DATA` — path for config files (where `controllers.yaml` is stored); default `~/.local/share/juju`.

## Caveats from the juju/juju issue tracker

- **[#19270](https://github.com/juju/juju/issues/19270) (open, kind/bug, state/blocked)** — if `JUJU_CONTROLLER` is set in the environment, `juju switch` fails with:
  ```
  ERROR cannot switch when JUJU_CONTROLLER is overriding the controller (set to "<controller name>")
  ```
  Don't rely on the env var if you also use `juju switch`; use `-c` per-command instead. Workaround: `JUJU_CONTROLLER="" juju switch …`.

- **[#18729](https://github.com/juju/juju/issues/18729) (closed)** — killing a k8s Juju controller directly can break permissions for *other* controllers on the *same* k8s cluster. Doesn't apply to your setup (separate clouds: machines vs Canonical Kubernetes), but worth noting if you ever host multiple controllers on one CK8s.

- There is **no documented "fan-out to all controllers" mode** — a single command always targets exactly one controller. Running things in both controllers "simultaneously" means concurrent CLI invocations each using `-c`.

## Practical recommendation

Keep `jujuc-vm-36-27` (or whichever you use most) as the active controller, and invoke the other with explicit `-c jujuc-ck8s-36-27` / `-m jujuc-ck8s-36-27:<model>` per command. **Avoid setting `JUJU_CONTROLLER` in your shell** due to #19270.

## Sources

- Juju CLI docs (overview): https://canonical.com/juju/docs/juju-cli/
- How to manage controllers: https://documentation.ubuntu.com/juju/latest/howto/manage-controllers/
- `juju switch` reference: https://documentation.ubuntu.com/juju/latest/reference/juju-cli/list-of-juju-cli-commands/switch/
- `juju` environment variables: https://documentation.ubuntu.com/juju/latest/reference/juju-cli/juju-environment-variables/
- juju/juju issues: https://github.com/juju/juju/issues/
