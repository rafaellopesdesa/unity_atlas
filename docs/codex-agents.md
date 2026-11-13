Run Codex **inside the allocated EL9 container**, after selecting your ATLAS release. Its shell commands can then compile and run your analysis with the same software you use interactively. Add two per-user stdio MCP servers so Codex can query Rucio and AMI using your own grid identity.

This workflow needs no facility-wide credential broker and no change to Unity login. You authenticate to Codex separately from ATLAS, create a short-lived VOMS proxy yourself, and let Codex start the MCP processes when needed.

## 1. What runs where {#overview}

| Component | Environment and purpose |
| --- | --- |
| Codex CLI | Runs in EL9 on your allocated compute node, in your analysis directory. Its shell commands inherit the ATLAS release environment. |
| Rucio and AMI MCP servers | Child processes started by Codex in the same container, under your Unix account. They communicate over stdin/stdout; there is no listening HTTP port. |
| MCP Python environment | A separate Pixi environment containing the clients and grid dependencies. It does not replace the Python used by your analysis. |
| VOMS proxy | A short-lived file created by you before starting Codex; both MCP servers use it to authenticate as you. |

You need a Unity account and group work directory, an OpenAI sign-in method enabled for Codex, an active ATLAS grid identity, and a valid grid certificate/private key. Your certificate identity must be registered for the ATLAS services you use. A Unity login, CERN password, or Codex login does not replace the grid credential.

Complete [Setting up the environment](../setting-up-environment/) first, including the one-time creation of your work/project directories and the [`.bashrc` configuration](../setting-up-environment/#bashrc), then [install Pixi](../using-pixi/#installation). This chapter uses your saved `USER_PI` and `ATLAS_WORKDIR`, Unity `$USER`, and the `unity_cpu`, `unity_gpu`, `setupATLAS`, and `atlas_gpu` commands.

The compute node needs outbound connectivity to the sign-in/model service and ATLAS endpoints; installation additionally needs access to the package sources. This chapter starts with **dataset discovery and metadata queries**: Rucio MCP is explicitly launched in read-only mode.

## 2. Allocate resources and enter EL9 {#container}

From your computer, connect using the [local SSH configuration from Using VS Code](../using-vscode/#configure-your-local-computer):

```bash
ssh unity
```

For a session that can survive an SSH disconnect, start `tmux new -s atlas-codex` on the login node first and record its hostname, following the [session guidance](../setting-up-environment/#sessions). Then request resources:

```bash
# Unity login node
unity_cpu
```

The default helper requests four CPUs, 16 GB of memory, and two hours. Once Unity gives you a compute-node shell, check `hostname -f` and `echo "$SLURM_JOB_ID"`, then start the container. If this new shell has not loaded your configuration, run `source ~/.bashrc` first.

```bash
# Ubuntu compute node
module load apptainer/latest
cd "$ATLAS_WORKDIR"
setupATLAS -c el9
```

For GPU analysis, use this alternative sequence. `unity_gpu` requests one GPU with the same CPU, memory, and time limits; `atlas_gpu` loads Apptainer and supplies the GPU passthrough options from the [environment chapter](../setting-up-environment/#gpu):

```bash
# Unity login node
unity_gpu

# After allocation, on the Ubuntu GPU compute node
cd "$ATLAS_WORKDIR"
atlas_gpu
```

`/work` is normally visible inside the container without an additional `-m /work`. If a required path is missing, follow the [mount guidance](../setting-up-environment/#container).

Inside EL9, explicitly enter your analysis work area and check the environment:

```bash
# Inside EL9
cd "$ATLAS_WORKDIR"
cat /etc/os-release
uname -m
printf 'Container home: %s\n' "$HOME"
```

This chapter targets **x86_64** nodes. On the first visit, install the tools in this fresh container before running `asetup`. On later visits, reuse the installation and go to [Prepare a proxy](#grid-auth), then [Load ATLAS and start Codex](#start).

## 3. Install Codex and sign in {#codex-install}

Run the official standalone installer **inside EL9**. It does not require Node.js or a Python environment:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
codex --version
```

The installer currently uses `~/.local/bin`. Keep the installation in a persistent directory visible in future containers. If the launcher changes the apparent home directory, use the paths visible **inside EL9** consistently.

Use device authentication on the remote node:

```bash
codex login --device-auth
codex login status
```

Open the printed URL on your own computer and enter the one-time code. This requires device-code authentication to be enabled in the relevant ChatGPT account/workspace settings. If it is unavailable, use the alternatives in the [official authentication guide](https://developers.openai.com/codex/auth/), or ask the workspace administrator to enable the supported flow. You do not need a browser running on the compute node.

Codex normally retains the login in its configured credential store, so a new allocation does not imply a new login. Keep its configuration and credentials private; do not put them in your analysis repository. This authentication is only for Codex—ATLAS authentication comes below.

## 4. Install isolated MCP tools {#mcp-install}

Use a dedicated Pixi environment for the MCP servers. In particular, **do not `pip install` them into the Python selected by `asetup`**, and do not activate their environment in your analysis shell. Their dependency versions serve the catalog clients, while analysis code must keep the release's Python and ROOT libraries.

This section assumes Pixi is installed as described in [Using Pixi](../using-pixi/#installation). Check that the installation is visible inside EL9:

```bash
"$HOME/.pixi/bin/pixi" --version
```

The workflow uses a supplied manifest, following the earlier chapter's [existing-project instructions](../using-pixi/#projects). Download the [manifest](../examples/codex/pixi.toml) and [environment launcher](../examples/codex/atlas-mcp-env.sh) to the same private directory:

```bash
MCP_DIR="$HOME/.local/share/unity-atlas-mcp"
install -d -m 700 "$MCP_DIR"
curl --fail --location \
  https://raw.githubusercontent.com/rafaellopesdesa/unity_atlas/main/examples/codex/pixi.toml \
  --output "$MCP_DIR/pixi.toml"
curl --fail --location \
  https://raw.githubusercontent.com/rafaellopesdesa/unity_atlas/main/examples/codex/atlas-mcp-env.sh \
  --output "$MCP_DIR/atlas-mcp-env.sh"
chmod u+x "$MCP_DIR/atlas-mcp-env.sh"
```

The manifest uses conda-forge packages, including pyAMI through the AMI package's dependencies, and pins the MCP versions:

```toml
[workspace]
name = "atlas-mcp"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
python = "3.11.*"
rucio-mcp = "==0.10.0"
ami-mcp = "==0.3.1"
voms = "*"
voms-lsc = "*"
ca-policy-lcg = "*"
```

Install before the first MCP handshake, so Codex does not need to wait for dependency resolution and downloads:

```bash
env -i HOME="$HOME" USER="$(id -un)" PATH=/usr/bin:/bin LANG=C.UTF-8 \
  "$HOME/.pixi/bin/pixi" install --manifest-path "$MCP_DIR/pixi.toml"
```

Keep the generated `pixi.lock` with the manifest; the launcher uses `--locked` to prevent silent re-resolution at server startup. Pixi generates this lock file during installation. If home quota is limited, choose a private persistent work directory for `MCP_DIR` **before downloading and installing**. Use that directory in every subsequent `MCP_DIR` assignment and in the absolute launcher paths below.

The launcher starts Pixi with an explicit clean environment and forwards only the relevant proxy/account settings. This keeps ATLAS `PYTHONPATH`, `PYTHONHOME`, and `LD_LIBRARY_PATH` out of the MCP clients. Pixi then activates its own grid CA environment. Codex's parent shell remains unchanged. Do not add `pixi run --clean-env` to this launcher: that additional filter can remove the explicitly forwarded grid variables.

If Pixi is installed elsewhere, set `ATLAS_MCP_PIXI` to its absolute executable path, and substitute that path in the installation command. The launcher accepts this override.

Check that the installed packages import and their command-line interfaces work:

```bash
"$MCP_DIR/atlas-mcp-env.sh" python -c \
  'import sys, importlib.metadata as m, pyAMI.client, rucio.client; print(sys.version); print("rucio-mcp", m.version("rucio-mcp")); print("ami-mcp", m.version("ami-mcp"))'
"$MCP_DIR/atlas-mcp-env.sh" voms-proxy-init --help
```

These are installation checks, not authenticated service tests.

## 5. Prepare a personal grid proxy {#grid-auth}

Perform authentication yourself in the terminal **before starting Codex**. The MCP servers must not stop during their stdin/stdout protocol to ask for a private-key passphrase.

Have your existing ATLAS-registered grid certificate and encrypted private key available as `~/.globus/usercert.pem` and `~/.globus/userkey.pem` **inside this container**, with restrictive permissions on the key. If these are not already on Unity, transfer your existing files through your normal SSH/file-transfer workflow. If you do not yet have a grid certificate, follow the ATLAS instructions for [obtaining a certificate](https://atlas-software.docs.cern.ch/analysis/analysis_tutorial/basicSetup/grid_cert/) and [installing and registering it](https://atlas-software.docs.cern.ch/analysis/analysis_tutorial/basicSetup/grid_setup/) first; the commands below do not issue or register a certificate.

Check the paths **inside EL9**; the container may expose your home at a different path than the Ubuntu host. The proxy commands below pass the certificate and key paths explicitly with `-cert` and `-key`. If your files have different names or locations, substitute their paths as visible inside the container in each command, including renewal.

```bash
printf 'HOME=%s\n' "$HOME"
ls -l "$HOME/.globus/usercert.pem" "$HOME/.globus/userkey.pem"
chmod 700 "$HOME/.globus"
chmod 600 "$HOME/.globus/userkey.pem"
```

Create a private session directory in the container's `/tmp`, choose the proxy path, and enter your **Rucio account name**, which may differ from your Unity username:

```bash
umask 077
export ATLAS_PROXY_DIR="$(mktemp -d /tmp/atlas-proxy.XXXXXXXX)"
export X509_USER_PROXY="$ATLAS_PROXY_DIR/x509up"
export RUCIO_ACCOUNT=YOUR_RUCIO_ACCOUNT
MCP_DIR="$HOME/.local/share/unity-atlas-mcp"

"$MCP_DIR/atlas-mcp-env.sh" voms-proxy-init -voms atlas -valid 12:00 \
  -cert "$HOME/.globus/usercert.pem" \
  -key "$HOME/.globus/userkey.pem" \
  -out "$X509_USER_PROXY"
"$MCP_DIR/atlas-mcp-env.sh" voms-proxy-info \
  -file "$X509_USER_PROXY" -timeleft
```

The passphrase prompt unlocks your grid private key; it is not asking for your Unity or Codex password. The last command must report a positive remaining lifetime. A requested 12-hour lifetime is a request, not a guarantee—inspect the actual expiry.

The proxy stays on this node/container and is passed to the clients by **filename**, not by putting its contents into the conversation or configuration. Recreate it after moving to another node or a container with a different `/tmp`. The original certificate/key and the short-lived proxy are different files.

The MCP `rucio_whoami` check below will verify the actual service-side account. The server's `--site atlas` selects its bundled ATLAS configuration.

## 6. Give Codex the MCP configuration {#configuration}

Print the launcher's absolute path:

```bash
printf '%s\n' "$MCP_DIR/atlas-mcp-env.sh"
mkdir -p "$HOME/.codex"
```

Merge the following into your existing **`~/.codex/config.toml` inside EL9** ([download the example](../examples/codex/config.toml)). Replace each complete `command` value with the absolute launcher path printed above. TOML command paths are literal: do not put `$HOME` in them. If you already have any of these tables, edit them instead of adding duplicate tables. Put the top-level settings before the first table header.

```toml
# Merge into your existing ~/.codex/config.toml; do not replace it blindly.
# Top-level settings must appear before any [table] headers.
approval_policy = "on-request"
sandbox_mode = "workspace-write"
allow_login_shell = false

[shell_environment_policy]
inherit = "all"
ignore_default_excludes = false

[mcp_servers.atlas-rucio]
command = "/ABSOLUTE/HOME/.local/share/unity-atlas-mcp/atlas-mcp-env.sh"
args = ["rucio-mcp", "serve", "--site", "atlas", "--auth-type", "x509", "--read-only"]
env_vars = ["X509_USER_PROXY", "RUCIO_ACCOUNT", "ATLAS_MCP_PIXI", "ATLAS_PMGXSEC_PATH"]
startup_timeout_sec = 120
tool_timeout_sec = 120

[mcp_servers.atlas-ami]
command = "/ABSOLUTE/HOME/.local/share/unity-atlas-mcp/atlas-mcp-env.sh"
args = ["ami-mcp", "serve"]
env_vars = ["X509_USER_PROXY", "ATLAS_MCP_PIXI", "ATLAS_PMGXSEC_PATH"]
startup_timeout_sec = 120
tool_timeout_sec = 120
```

The settings serve two different environments:

- `allow_login_shell = false` and `inherit = "all"` preserve the exported ATLAS setup when Codex runs analysis commands. The explicit default-exclusion setting filters variable names containing `KEY`, `SECRET`, or `TOKEN`; it does not prevent processes from reading files accessible to your account.
- Each MCP server's `env_vars` forwards the **current** proxy path at startup. A new allocation can use a new path without rewriting the TOML. The wrapper isolates the server's Python environment.
- `--read-only` blocks Rucio MCP write operations. AMI's standard tools are oriented toward metadata queries; AMI's own role permissions remain authoritative. These settings do not impose a separate read-only restriction on Codex's general shell.

These user-level settings apply to other Codex sessions using the same configuration. Codex also supports project-scoped `.codex/config.toml` in trusted projects if you prefer to scope the ATLAS-specific settings; keep personal absolute paths out of shared commits.

Verify the entries:

```bash
codex mcp list
codex mcp get atlas-rucio
codex mcp get atlas-ami
```

These commands confirm registration, not successful grid access. **Do not run `codex mcp login` for these stdio servers**; that command is for compatible HTTP/OAuth servers. Their authentication is the VOMS proxy you just created.

Codex will launch both commands itself. You do not need to keep two extra terminals open running `rucio-mcp serve` and `ami-mcp serve`, start them in the background, or expose a network port. A manually started stdio server waiting silently for protocol input is not an interactive command prompt.

## 7. Load ATLAS and start Codex {#start}

In the same EL9 shell, enter your existing analysis checkout. Replace `PROJECT_NAME` with its directory name, as in the Pixi and JupyterLab chapters. Select the full `project,version` release string described in [Load analysis software](../setting-up-environment/#software), then source any generated local build setup:

```bash
cd "$ATLAS_WORKDIR/PROJECT_NAME"
read -r -p 'ATLAS project,version: ' ATLAS_RELEASE
if [[ "$ATLAS_RELEASE" == *,* ]]; then
    asetup "$ATLAS_RELEASE"
else
    echo 'Enter a project and exact version, separated by a comma.'
fi
# If needed, use your real generated setup path:
# source /absolute/path/to/build/PLATFORM/setup.sh
```

**Continue only after the release and build setup succeed.** Then start Codex from that project directory:

```bash
export PATH="$HOME/.local/bin:$PATH"
export OMP_NUM_THREADS=4
python -c 'import sys, ROOT; print(sys.executable); print(ROOT.gROOT.GetVersion())'
codex --sandbox workspace-write --ask-for-approval on-request
```

Set the thread count to fit your actual allocation. Run `nvidia-smi` and a small framework-specific check before GPU work. Starting Codex on Ubuntu and later entering a container in one subprocess will not relocate the running agent and its other processes.

The default workspace is the directory where you start Codex. If a necessary output directory lies elsewhere, add that particular directory with `--add-dir /absolute/output/path`. Keep heavy builds, event loops, and training within the Slurm allocation.

Inside Codex, use `/mcp` to inspect the active connections. Start with this small validation request:

> Verify that you are on the allocated compute node in EL9. Report the working directory, Python executable, ATLAS project/version, and ROOT version using a non-login shell. Run a small PyROOT histogram check. Then use atlas-rucio to call rucio_whoami and report my Rucio account. Do not print the environment or any credential contents.

For AMI, use a real dataset already relevant to your analysis:

> Use atlas-ami to retrieve metadata and provenance for DATASET_NAME. Make a bounded query to the remote AMI service and report the result or exact error. Do not substitute a local PMG cross-section lookup for this authentication test.

Replace `DATASET_NAME` before sending it. A PMG file lookup on CVMFS can succeed without authenticating to AMI, so it is not sufficient for this test. Once both checks work, ask for a bounded discovery task, then for analysis code using the returned dataset names. Large downloads, replication-rule changes, and production submissions should be separate explicit tasks.

Codex's shell sandbox and the MCP processes have separate execution paths. Shell network restrictions do not themselves restrict MCP network traffic; there is no need to enable unrestricted shell networking solely for the catalog clients. Their service credentials and server capabilities control those calls.

## 8. Give the agent project context {#project-context}

Add instructions to your project's `AGENTS.md`; merge with any existing file. A starter is available as [AGENTS.md.example](../examples/codex/AGENTS.md.example). Tell Codex which release is already active, how to build/test the project, which inputs to use, and how many resources the job has. The model does not automatically know the contents of our ChatGPT conversation.

A short `PROJECT_CONTEXT.md` is useful for changing details:

```markdown
# Project context

- Goal: describe the analysis task.
- Release: exact project, release, and platform used by the analysis.
- Build setup: absolute path, or none.
- Input data: exact paths or dataset names; nominate a small test sample.
- Outputs: the intended writable project/output directory.
- Resources: allocated CPUs, memory, GPUs, and wall time.
- Validation: the command and expected result for a small successful test.
- Current status: completed work, known problems, and the next task.
```

Keep credentials out of these files. For example, ask: “Read AGENTS.md and PROJECT_CONTEXT.md, inspect the existing analysis, implement the next step, and run the small validation sample.”

## 9. Renew, resume, and finish {#sessions}

If the proxy expires, leave Codex and renew it **in the same terminal, at the same path**:

```bash
"$MCP_DIR/atlas-mcp-env.sh" voms-proxy-init -voms atlas -valid 12:00 \
  -cert "$HOME/.globus/usercert.pem" \
  -key "$HOME/.globus/userkey.pem" \
  -out "$X509_USER_PROXY"
"$MCP_DIR/atlas-mcp-env.sh" voms-proxy-info -file "$X509_USER_PROXY" -timeleft
codex resume --last
```

Restarting Codex also restarts its stdio servers, which avoids keeping a client authenticated with an expired credential. The `env_vars` values are read when the servers start. Use `codex resume` to choose a saved conversation instead of automatically selecting the last one.

If the allocation ended, first obtain a **new allocation**, enter EL9, create a new proxy, re-export your Rucio account, and select the same ATLAS release/build. Then resume from the project directory. Resuming restores conversation history, not the old process, container, GPU allocation, or software environment.

With `tmux`, detach using **Ctrl+B**, then **D**, and reconnect to the same login node before `tmux attach -t atlas-codex`. The Slurm time limit still applies.

When finished, exit Codex, remove the session proxy, and then leave the container and allocation:

```bash
"$MCP_DIR/atlas-mcp-env.sh" voms-proxy-destroy -file "$X509_USER_PROXY"
rmdir "$ATLAS_PROXY_DIR"
unset X509_USER_PROXY ATLAS_PROXY_DIR
exit
# Back in the allocation's Ubuntu shell: exit again to release it.
```

Destroying a local proxy file removes that copy; it does not revoke every token already issued using it. The workflow relies on short-lived credentials and ending the associated client processes.

### Short sequence for later sessions

After obtaining resources and entering a fresh EL9 container, return to the same checkout and recreate the proxy:

```bash
cd "$ATLAS_WORKDIR/PROJECT_NAME"
MCP_DIR="$HOME/.local/share/unity-atlas-mcp"
umask 077
export ATLAS_PROXY_DIR="$(mktemp -d /tmp/atlas-proxy.XXXXXXXX)"
export X509_USER_PROXY="$ATLAS_PROXY_DIR/x509up"
export RUCIO_ACCOUNT=YOUR_RUCIO_ACCOUNT
"$MCP_DIR/atlas-mcp-env.sh" voms-proxy-init -voms atlas -valid 12:00 \
  -cert "$HOME/.globus/usercert.pem" \
  -key "$HOME/.globus/userkey.pem" \
  -out "$X509_USER_PROXY"
"$MCP_DIR/atlas-mcp-env.sh" voms-proxy-info -file "$X509_USER_PROXY" -timeleft
read -r -p 'ATLAS project,version: ' ATLAS_RELEASE
if [[ "$ATLAS_RELEASE" == *,* ]]; then
    asetup "$ATLAS_RELEASE"
else
    echo 'Enter a project and exact version, separated by a comma.'
fi
# Source your local build setup here if needed.
```

Once the proxy, release, and local build setup are ready, resume:

```bash
export PATH="$HOME/.local/bin:$PATH"
export OMP_NUM_THREADS=4
python -c 'import ROOT; print(ROOT.gROOT.GetVersion())'
codex resume
```

Installation, MCP registration, and Codex login normally persist. The allocation, container, software setup, and proxy do not. Optional `.bashrc` additions should define helpers or add the Codex executable directory to `PATH`; do not automatically start Codex, mint proxies, or enter containers at login.

## Troubleshooting {#troubleshooting}

| Symptom | What to check |
| --- | --- |
| `codex: command not found` inside EL9 | Add the actual installation directory to `PATH` inside the container. Check whether the host and container expose different home paths. |
| Device login is unavailable | Check account/workspace device-code settings and the official alternative authentication flows. Codex login is independent of VOMS authentication. |
| ROOT works in your shell but fails in Codex | Start Codex after `asetup`; check non-login shell settings and inherited Python/library paths. Do not activate the MCP environment in the analysis shell. |
| Pixi cannot resolve/install | Confirm x86_64/EL9, package-source connectivity, quota, and the downloaded manifest. Preserve the error; do not solve it by installing into the ATLAS release. |
| MCP initialization fails | Check the absolute executable path, executable permission, installed lock file, forwarded proxy/account variables, and `/mcp` error details. No startup banner may be printed to stdout by the launcher. |
| VOMS reports `No credentials found!` | Check `HOME` and the certificate/key filenames inside EL9. Pass their readable paths explicitly with `-cert` and `-key`, as in [Prepare a personal grid proxy](#grid-auth). A `.globus` directory in your current working directory is not necessarily `$HOME/.globus`. If the error persists, inspect any preceding credential-loading error. |
| VOMS cannot load the key or reports a bad passphrase | Check key permissions, file format, and the grid-key passphrase. For later authentication failures, also check certificate expiry and ATLAS registration. |
| Rucio reports a wrong/unknown account | Use the Rucio account associated with your grid identity, not automatically your Unity username. |
| Proxy renewed but calls still fail | Check remaining lifetime and restart Codex so both stdio clients are recreated. A new node/container needs a newly accessible proxy path. |
| TLS validation reports expired CRLs | Refresh the writable Pixi CA bundle using the command below, then retry. Do not disable TLS verification. |
| Linux sandbox fails inside Apptainer | The host may restrict nested namespaces/bubblewrap. Record the exact error and ask Unity support for the supported configuration. An Apptainer shell with home/work mounts is not itself a replacement for Codex's file-access sandbox. |

For an expired-CRL error, refresh the isolated tool environment's certificate revocation lists:

```bash
"$MCP_DIR/atlas-mcp-env.sh" sh -c '"$X509_CERT_DIR/refresh_crls.sh"'
```

## References {#references}

- OpenAI: [Codex CLI](https://developers.openai.com/codex/cli/), [authentication](https://developers.openai.com/codex/auth/), [MCP configuration](https://developers.openai.com/codex/mcp/), [configuration reference](https://developers.openai.com/codex/config-reference/), and [CLI commands](https://developers.openai.com/codex/cli/reference/).
- OpenAI: [permissions](https://learn.chatgpt.com/docs/permissions), [sandbox requirements](https://learn.chatgpt.com/docs/sandboxing), and [AGENTS.md instructions](https://developers.openai.com/codex/guides/agents-md/).
- [Rucio MCP](https://github.com/kratsg/rucio-mcp), its [configuration](https://github.com/kratsg/rucio-mcp/blob/main/docs/configuration.md), and [conda-forge package recipe](https://github.com/conda-forge/rucio-mcp-feedstock/blob/main/recipe/recipe.yaml).
- [AMI MCP](https://github.com/kratsg/ami-mcp), its [configuration](https://github.com/kratsg/ami-mcp/blob/main/docs/configuration.md), and [conda-forge package recipe](https://github.com/conda-forge/ami-mcp-feedstock/blob/main/recipe/recipe.yaml).
- [Pixi installation](https://pixi.prefix.dev/latest/installation/) and [lock files](https://pixi.prefix.dev/latest/workspace/lock_file/).
- Unity: [interactive jobs](https://docs.unity.rc.umass.edu/documentation/jobs/salloc/) and [SSH](https://docs.unity.rc.umass.edu/documentation/connecting/ssh/).

