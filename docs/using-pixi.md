Pixi installs software in your own directories and runs commands with the dependencies supplied by a project. No administrator privileges are needed. This chapter covers installing Pixi, managing personal command-line tools, and using an **existing** Pixi project.

Complete the [environment setup](../setting-up-environment/), including your work/project directories and `.bashrc` configuration, first. The examples use your saved `USER_PI`, Unity `$USER`, and allocation/container helpers.

| Use | Command | Where it applies |
| --- | --- | --- |
| Personal command-line tools | `pixi global` | Tools available to your account from any directory. |
| A project's supplied dependencies and commands | `pixi install` and `pixi run` | The project identified by its Pixi manifest. |

## 1. Install Pixi in your user area {#installation}

For the ATLAS workflows in this guide, use a **fresh EL9 container before running `asetup`**. Install and resolve packages in the operating-system environment where you intend to run them. Starting from the Unity login node:

```bash
unity_cpu

# After allocation, on the Ubuntu compute node:
module load apptainer/latest
cd "$ATLAS_WORKDIR"
setupATLAS -c el9
```

Inside EL9, run the official installer **once**:

```bash
curl -fsSL https://pixi.sh/install.sh | PIXI_NO_PATH_UPDATE=1 bash
export PATH="$HOME/.pixi/bin:$PATH"
pixi --version
```

The default executable is `~/.pixi/bin/pixi`. `PIXI_NO_PATH_UPDATE=1` leaves shell-file editing to you. Ensure your existing Unity `~/.bashrc` contains the following line **once**; it is also included in the environment chapter's [complete shell snippet](../setting-up-environment/#bashrc):

```bash
export PATH="$HOME/.pixi/bin:$PATH"
```

The export in the installation command makes Pixi available immediately. Future shells load the saved setting. If a new container resets `PATH`, run that export inside it, or invoke `"$HOME/.pixi/bin/pixi"` directly. Check that the container exposes the same persistent home directory; a new allocation should not require another installation.

To update the Pixi executable later, use `pixi self-update`. This is separate from updating the packages it manages. See the [official installation instructions](https://pixi.prefix.dev/latest/installation/) for alternative locations and platforms.

## 2. Manage personal tools with pixi global {#global-tools}

Here, **global means available throughout your own account**, not installed for everyone on Unity. Pixi normally creates a separate environment for each requested tool and exposes its executable through `~/.pixi/bin`.

For example, install the text-search tool ripgrep from conda-forge:

```bash
pixi global install --channel conda-forge ripgrep
rg --version
```

The package is named `ripgrep`, while its command is `rg`. You can now run `rg` from any directory without `pixi run` or an activation step.

| Task | Command |
| --- | --- |
| List your global tools/environments | `pixi global list` |
| Update the installed ripgrep environment | `pixi global update ripgrep` |
| Remove that environment and its exposed command | `pixi global uninstall ripgrep` |

Use global installation for utilities you want across projects. Installing a global tool does not add it to a project's manifest. The [global-tools guide](https://pixi.prefix.dev/latest/global_tools/introduction/) covers additional options.

## 3. Install an existing project's dependencies {#projects}

A Pixi-enabled repository supplies a **manifest**, usually `pixi.toml` or a `pyproject.toml` containing Pixi configuration. It often also supplies `pixi.lock`, which records the resolved package versions. You do not need to create or edit either file just to run that project.

Place the repository in your work area. For a project already checked out under `PROJECT_NAME`, run:

```bash
# Inside a fresh EL9 shell; replace PROJECT_NAME with your repository directory.
cd "/work/${USER_PI}/${USER}/atlas/PROJECT_NAME"
pixi install
```

`pixi install` prepares the default environment, normally under the project's `.pixi/envs/` directory. It uses an up-to-date lock file; if the lock is missing or needs updating, it can resolve dependencies and write the lock. Downloads and environments consume your storage quota, so keep substantial project environments in your work area.

When the project provides a lock file and you want to require it unchanged, use:

```bash
pixi install --locked
```

`--locked` fails if the lock is missing or inconsistent with the manifest. Follow the project's instructions to resolve that situation. Keep the manifest and lock together when sharing a project; the installed `.pixi` directory can be recreated from them.

## 4. Run the project's code {#run}

Prefix a command with `pixi run` to execute it in the project's environment. For a repository whose manifest includes Python and which supplies an `analysis.py` script:

```bash
# In the project's directory, after pixi install:
pixi run python -c 'import sys; print(sys.executable)'
pixi run python analysis.py
```

Replace `analysis.py` with the command documented by your project. The printed Python path should identify the project's environment. No shell activation is required, and your parent shell remains unchanged when the command finishes. `pixi run` can install missing dependencies automatically, but an explicit `pixi install` makes the setup step clear.

Projects can also provide named tasks. List them with `pixi task list`; if the project defines a task named `test`, run it with `pixi run test`.

For a run using the supplied lock:

```bash
pixi run --locked python analysis.py
```

To select a manifest explicitly, use `--manifest-path` with either command:

```bash
pixi install --manifest-path "$ATLAS_WORKDIR/PROJECT_NAME/pixi.toml"
pixi run --manifest-path "$ATLAS_WORKDIR/PROJECT_NAME/pixi.toml" python --version
```

The manifest selects the environment; follow the project's working-directory instructions for code that opens relative paths. Keep builds, event processing, and training inside your Slurm allocation. Pixi does not allocate CPUs, GPUs, or additional wall time.

For notebooks, [Using JupyterLab](../using-jupyterlab/) shows how to launch the server from this environment and connect from your browser through SSH.

## 5. Use Pixi alongside ATLAS {#atlas}

Continue to use `asetup` for an ATLAS release and its Python/ROOT stack. Use Pixi for projects and supporting tools that supply their own dependencies. Installing another Python or ROOT globally can change which executable your shell finds; use project environments for those packages.

Separate package environments do not automatically remove every inherited variable. An existing ATLAS `PYTHONPATH` or `LD_LIBRARY_PATH` can interfere with an independent Pixi program. Start those workflows in a fresh EL9 shell before `asetup`, unless the project documents a combined setup.

The [Codex Agents chapter](../codex-agents/#mcp-install) provides such a combined workflow: Codex inherits the ATLAS release, while a launcher runs the Rucio/AMI clients in a separate Pixi environment with an explicitly cleaned environment. It reuses the Pixi installation from this chapter.

## Learn how to create and modify environments {#learn-more}

For a guided introduction to creating a Pixi project, adding dependencies, and maintaining its environment, follow **[The Carpentries: Introduction to Pixi](https://carpentries-incubator.github.io/pixi-introduction/)**. This manual focuses on installing tools and running environments supplied by an analysis or service.

References: [installation](https://pixi.prefix.dev/latest/installation/), [global tools](https://pixi.prefix.dev/latest/global_tools/introduction/), [`pixi install`](https://pixi.prefix.dev/latest/reference/cli/pixi/install/), [`pixi run`](https://pixi.prefix.dev/latest/reference/cli/pixi/run/), and [lock files](https://pixi.prefix.dev/latest/workspace/lock_file/).

**Next:** [Using VS Code](../using-vscode/) covers interactive editing and ATLAS Python execution on Unity.

Documentation reviewed: **8 November 2026**. Local checks cover the rendered links and Bash syntax; package installation and execution on Unity remain to be tested.
