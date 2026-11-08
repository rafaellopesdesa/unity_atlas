VS Code can edit files on Unity and run Python with ATLAS software inside EL9. The key is **where the remote VS Code backend starts**: opening an EL9 shell in an Ubuntu VS Code terminal changes that terminal, but does not move the Python extension, debugger, or notebook kernel into the container.

This chapter includes the Unity connection steps and three ways to work. For integrated ATLAS Python execution, start with the **container tunnel** method; it starts VS Code from the environment you have already prepared.

::: {.callout}
**Validation status.** The underlying interactive EL9 and NVIDIA passthrough recipes have been tested on Unity. The VS Code workflows below have been checked against the upstream documentation and locally checked for syntax and launcher behavior, but still need end-to-end tests on Unity. In particular, test Python Run, debugging, and reconnection before relying on either container backend for a long session.
:::

## Choose a connection method

| Method | Where the VS Code backend runs | ATLAS Python integration |
| --- | --- | --- |
| [A. Ordinary Remote SSH](#ordinary-ssh) | Ubuntu on your allocated compute node | Edit files and run ATLAS commands in a container terminal. Run/debug buttons need a container backend; a separate remote Jupyter server is another option for notebooks. |
| [B. Remote SSH into EL9](#container-ssh) | EL9, entered by an SSH startup command | Python execution and debugging in the container. Uses Unity's SSH route, with an additional launcher. Start with a CPU allocation. |
| [C. Remote Tunnels inside EL9](#container-tunnel) | EL9, launched from your configured ATLAS shell | Python execution and debugging in the container. Also the preferred first test for GPUs, because it starts directly in the allocated GPU shell. Requires access to Microsoft's tunnel service. |

All three methods use a **Slurm compute allocation**. A remote connection does not reserve resources. Do not run analysis or a persistent analysis backend on a login node.

## Configure your local computer

Install [VS Code](https://code.visualstudio.com/) and Microsoft's **Remote – SSH** extension. You need a Unity account and an SSH key registered with Unity, as for a normal terminal connection. The following assumes that `ssh unity` will use that key without an interactive password prompt.

Edit your **local** SSH configuration: `~/.ssh/config` on Linux/macOS or `%USERPROFILE%\.ssh\config` on Windows. Replace `YOUR_USERNAME` and the key path with your Unity username and actual private key. Use the same username/key for both entries.

```sshconfig
Host unity
    HostName login.unityhpc.org
    User YOUR_USERNAME
    IdentityFile ~/.ssh/id_ed25519

Host *.unity.rc.umass.edu
    User YOUR_USERNAME
    IdentityFile ~/.ssh/id_ed25519
    ProxyJump unity
```

`ProxyJump` reaches the compute node through Unity's login service. Test the login connection in a local terminal:

```bash
ssh unity
```

If Windows OpenSSH reports `Corrupted MAC on input`, Unity documents adding `MACs hmac-sha2-512` to the affected SSH host entries. Apply that workaround only for that error.

The optional [Bash shortcuts](../setting-up-environment/#bashrc) are useful in interactive terminals. **Do not automatically run `salloc`, enter a container, or select an ATLAS release every time `.bashrc` is read.** SSH and VS Code also start noninteractive shells; keep these actions in functions that you call explicitly.

## Request a compute session {#allocation}

In the Unity login shell, request a single compute node. For example, for CPU work:

```bash
salloc --partition=cpu --nodes=1 --ntasks=1 \
  --cpus-per-task=4 --mem=16G --time=02:00:00
```

Or, for a GPU session, use this allocation instead:

```bash
salloc --partition=gpu --nodes=1 --ntasks=1 --gpus=1 \
  --cpus-per-task=4 --mem=16G --time=02:00:00
```

Wait for the allocation. Unity's interactive setup puts you in a shell on the allocated node. Record the hostname and job ID, then choose a writable group work directory:

```bash
hostname -f
printf 'Job: %s\n' "$SLURM_JOB_ID"
export ATLAS_WORKDIR="/work/pi_YOUR_PI/$USER/atlas"
mkdir -p "$ATLAS_WORKDIR"
cd "$ATLAS_WORKDIR"
```

Replace `pi_YOUR_PI` with your actual group directory. Keep this allocation shell open. A `tmux` session on the login node, started before `salloc`, can protect it from a local network interruption; it does not extend the job's time limit.

The examples below use **job `123456`** and **`cpu001.unity.rc.umass.edu`** as placeholders. Substitute the values from your allocation. Refresh them every time you start a new job.

## A. Ordinary Remote SSH {#ordinary-ssh}

1. In local VS Code, open the Command Palette and run **Remote-SSH: Connect to Host…**.
2. Enter the full hostname of your **allocated compute node**, for example `cpu001.unity.rc.umass.edu`. Select **Linux** if prompted.
3. In the remote window, use **File → Open Folder…** and open your `/work/.../atlas` directory. The status bar should identify the compute-node SSH connection.
4. Open an integrated terminal and check `hostname -f`. To obtain an explicit shell in the existing job, use Unity's documented command with your job ID:

```bash
srun --overlap --pty --jobid=123456 /bin/bash
```

### Enter EL9 and select ATLAS software {#enter-el9}

For a CPU session, run in the allocated Ubuntu shell:

```bash
module load apptainer/latest
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" -c el9
```

For a GPU session, use the following **instead**. The `--nv` option makes the host NVIDIA driver components and utilities available inside Apptainer. Preserve Slurm's device selection rather than assigning a new GPU number:

```bash
module load apptainer/latest
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
(
    export ALRB_CONT_CMDOPTS="${ALRB_CONT_CMDOPTS:+$ALRB_CONT_CMDOPTS }--nv"
    if [[ ${CUDA_VISIBLE_DEVICES+x} ]]; then
        export APPTAINERENV_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
        export SINGULARITYENV_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
    fi
    if [[ ${CUDA_DEVICE_ORDER+x} ]]; then
        export APPTAINERENV_CUDA_DEVICE_ORDER="$CUDA_DEVICE_ORDER"
        export SINGULARITYENV_CUDA_DEVICE_ORDER="$CUDA_DEVICE_ORDER"
    fi
    source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" -c el9
)
```

If you installed the earlier `.bashrc` helpers, `atlas_gpu` is the shorter interactive equivalent. Unity already exposes `/work` in the tested ALRB setup, so an additional `-m /work` is not normally needed.

Now, **inside EL9**, select the exact release used by your analysis:

```bash
cat /etc/os-release
cd /work/pi_YOUR_PI/YOUR_USERNAME/atlas
asetup AnalysisBase,REPLACE_WITH_YOUR_TESTED_VERSION
python -c 'import sys, ROOT; print(sys.executable); print(ROOT.gROOT.GetVersion())'
```

Use your actual project/release instead of the placeholder. If you have a compiled analysis package, also source its generated setup script after `asetup`, for example `source /absolute/path/to/build/PLATFORM/setup.sh`. On a GPU allocation, check `nvidia-smi`; if the utility is not on `PATH`, try `/usr/bin/nvidia-smi`, as described in the [GPU troubleshooting notes](../setting-up-environment/#troubleshooting).

You can now run analysis commands in this terminal. **The VS Code backend is still on Ubuntu.** Selecting a Python binary on CVMFS does not by itself provide EL9 or the environment established by `asetup`. Continue with B or C for integrated execution.

## B. Remote SSH directly into EL9 {#container-ssh}

ATLAS documents using SSH `RemoteCommand` to enter a container **before VS Code starts its backend**. The adaptation below selects your ATLAS release at that stage too. No SSH daemon inside the container is required.

Start with a **CPU allocation**, with only one running job of yours on that node. Unity's SSH service must place the session in the allocation; the launcher's job check detects stale or ambiguous configuration but does not replace that site-level behavior. For GPU work, use method C initially: a new SSH session may have a different Slurm step/device view from the original GPU shell.

### Install the launchers

In your Unity Ubuntu shell, download both companion scripts to the same directory:

```bash
mkdir -p "$HOME/.local/bin"
curl --fail --location \
  https://raw.githubusercontent.com/rafaellopesdesa/unity_atlas/main/examples/vscode/atlas-vscode-ssh.sh \
  --output "$HOME/.local/bin/atlas-vscode-ssh.sh"
curl --fail --location \
  https://raw.githubusercontent.com/rafaellopesdesa/unity_atlas/main/examples/vscode/atlas-vscode-shell.sh \
  --output "$HOME/.local/bin/atlas-vscode-shell.sh"
chmod u+x "$HOME/.local/bin/atlas-vscode-ssh.sh"
```

The [host launcher](../examples/vscode/atlas-vscode-ssh.sh) loads Apptainer and explicitly binds CVMFS, `/work`, and your home directory. The [inside-container launcher](../examples/vscode/atlas-vscode-shell.sh) sets up ATLAS and then passes SSH's input stream to Bash for VS Code's bootstrap. Setup output goes to stderr; setup commands cannot consume that input stream.

### Save this allocation's settings

First run the normal EL9 setup above once and record the **resolved EL9 container image path printed by ALRB**. Use that actual path, which may be a container directory on CVMFS, rather than guessing a container tag. Exit the container back to the **original CPU allocation's Ubuntu shell**, keeping the allocation alive.

Fill in the image and release below. Set `ATLAS_VSCODE_BUILD_SETUP` to your absolute generated build setup path if needed, or leave it empty. This writes a private, allocation-specific configuration file:

```bash
ATLAS_VSCODE_IMAGE='/cvmfs/REPLACE_WITH_THE_RESOLVED_EL9_IMAGE_PATH'
ATLAS_VSCODE_RELEASE='AnalysisBase,REPLACE_WITH_YOUR_TESTED_VERSION'
ATLAS_VSCODE_BUILD_SETUP=''
ATLAS_VSCODE_CONFIG="$ATLAS_WORKDIR/vscode-job-${SLURM_JOB_ID}.sh"
(
    umask 077
    {
        printf 'ATLAS_VSCODE_JOB_ID=%q\n' "$SLURM_JOB_ID"
        printf 'ATLAS_VSCODE_NODE=%q\n' "$(hostname -s)"
        printf 'ATLAS_VSCODE_CPUS=%q\n' "${SLURM_CPUS_PER_TASK:-1}"
        printf 'ATLAS_VSCODE_IMAGE=%q\n' "$ATLAS_VSCODE_IMAGE"
        printf 'ATLAS_VSCODE_RELEASE=%q\n' "$ATLAS_VSCODE_RELEASE"
        printf 'ATLAS_VSCODE_WORKDIR=%q\n' "$ATLAS_WORKDIR"
        printf 'ATLAS_VSCODE_BUILD_SETUP=%q\n' "$ATLAS_VSCODE_BUILD_SETUP"
    } > "$ATLAS_VSCODE_CONFIG"
)
printf 'Configuration: %s\n' "$ATLAS_VSCODE_CONFIG"
```

### Connect through a dedicated SSH alias

Add this entry to your **local** SSH configuration, replacing all placeholders, including the job ID in the configuration filename:

```sshconfig
Host unity-atlas-el9
    HostName cpu001.unity.rc.umass.edu
    User YOUR_USERNAME
    IdentityFile ~/.ssh/id_ed25519
    ProxyJump unity
    RemoteCommand ~/.local/bin/atlas-vscode-ssh.sh /work/pi_YOUR_PI/YOUR_USERNAME/atlas/vscode-job-123456.sh
    RequestTTY yes
```

Use paths without spaces in this SSH entry. Keep `RemoteCommand` on this dedicated alias, so normal Unity SSH access is unaffected. Do not put `srun --pty` in `RemoteCommand`: VS Code needs its bootstrap input intact, and the backend must survive the bootstrap shell exiting.

In **local VS Code User Settings (JSON)**, merge these settings with your existing configuration:

```json
{
  "remote.SSH.enableRemoteCommand": true,
  "remote.SSH.remoteServerListenOnSocket": false,
  "remote.SSH.lockfilesInTmp": true,
  "remote.SSH.serverInstallPath": {
    "unity-atlas-el9": "/work/pi_YOUR_PI/YOUR_USERNAME/atlas/.vscode-el9-ssh/job-123456"
  }
}
```

The separate server directory prevents reuse of the Ubuntu backend or an earlier allocation's environment. Refresh its job ID with the SSH entry. ATLAS notes that `RemoteCommand` support is experimental; the socket setting can be necessary for it.

First test the alias from a local terminal with `ssh unity-atlas-el9`. At its prompt, check `/etc/os-release` and run the Python/ROOT check above, then `exit`. Next run **Remote-SSH: Connect to Host… → unity-atlas-el9**, open your project folder, and follow the [integrated Python checks](#integrated-python). If VS Code bootstrap or reconnection fails, inspect **Output → Remote - SSH** and try method C.

## C. Start a VS Code tunnel inside EL9 {#container-tunnel}

This method starts Microsoft's standalone CLI **inside the already configured ATLAS environment**, so its remote backend and extensions run in EL9. It avoids the SSH startup wrapper. The desktop editor connects using **Remote – Tunnels**; a browser client is also available.

Use the **original compute shell created by your allocation**, especially for a GPU job. Follow [Enter EL9 and select ATLAS software](#enter-el9), including `--nv` for GPUs, `asetup`, and any local build setup. Confirm the Python/ROOT check succeeds before continuing.

Inside that configured EL9 shell, install the standalone CLI in your writable work directory. The download below is for **x86-64** nodes:

```bash
cd /work/pi_YOUR_PI/YOUR_USERNAME/atlas
VSCODE_ROOT="$PWD/.vscode-atlas"
install -d -m 700 "$VSCODE_ROOT" "$VSCODE_ROOT/cli-bin"
curl --fail --location \
  'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' \
  --output "$VSCODE_ROOT/vscode_cli.tar.gz"
tar -xf "$VSCODE_ROOT/vscode_cli.tar.gz" -C "$VSCODE_ROOT/cli-bin"

# Save this interpreter path for the VS Code selection step.
python -c 'import sys; print(sys.executable)'
```

Install once; on later sessions reuse the CLI and redefine `VSCODE_ROOT`. Start the tunnel in the foreground, replacing `123456` with your current job ID:

```bash
VSCODE_SESSION="$VSCODE_ROOT/sessions/job-123456"
install -d -m 700 "$VSCODE_SESSION"
"$VSCODE_ROOT/cli-bin/code" \
  --cli-data-dir "$VSCODE_SESSION/cli" \
  tunnel --server-data-dir "$VSCODE_SESSION/server" \
  --name unity-atlas-123456
```

Use the **explicit standalone CLI path**. A `code` command supplied by an existing Remote SSH terminal may instead be a shim for that existing session. Keep both state directories separate from other sessions: the CLI cache can otherwise reuse an already running server. Use a new session directory and tunnel name for simultaneous environments or a changed ATLAS release.

1. Follow the CLI's device-login instructions and review the VS Code Server license prompt. Sign in with the GitHub or Microsoft identity you will use in your editor.
2. In local VS Code, install Microsoft's **Remote – Tunnels** extension.
3. Run **Remote-Tunnels: Connect to Tunnel…**, sign in with the same identity, and select `unity-atlas-123456`.
4. Open `/work/pi_YOUR_PI/YOUR_USERNAME/atlas` and continue below. Alternatively, open the `vscode.dev` URL printed by the CLI to use the browser editor.

The compute node needs outbound access to Microsoft's tunnel service; if that service is unavailable from Unity, use the SSH method. Keep the allocation and foreground tunnel running. Stop the tunnel with **Ctrl+C** when finished. Do not install a persistent tunnel service on a compute node.

## Configure and test integrated Python {#integrated-python}

These steps apply to methods B and C. In the connected window, install Microsoft's **Python**, **Python Debugger**, and **Pylance** extensions **on the remote target** when prompted. Installing only the local extensions is insufficient.

In a new remote integrated terminal, without entering another container, check:

```bash
cat /etc/os-release
python -c 'import sys, ROOT; print(sys.executable); print(ROOT.gROOT.GetVersion())'
```

Run **Python: Select Interpreter → Enter interpreter path…** and select the full path printed by `sys.executable`. The selected interpreter needs the ATLAS environment as well as EL9. If terminal startup files overwrite `PATH`, `PYTHONPATH`, or library paths, they can also override the backend's inherited environment; correct those settings and restart the backend.

For an Athena development build, ATLAS also documents generated `ide_python` and `env.txt` settings for its Python tools. Those are build-specific additions; do not assume every AnalysisBase installation provides them.

### Run and debug a small analysis check

Create `check_atlas.py` in your project, or [download this example](../examples/vscode/check_atlas.py):

```python
"""Run with VS Code's Run button, debugger, and notebook kernel."""
import os
import sys
from pathlib import Path

import ROOT

ROOT.gROOT.SetBatch(True)
print(Path("/etc/os-release").read_text())
print("Python:", sys.executable)
print("ATLAS project:", os.environ.get("AtlasProject"))
print("ATLAS version:", os.environ.get("AtlasVersion"))
print("ROOT:", ROOT.gROOT.GetVersion())
print("CUDA_VISIBLE_DEVICES:", os.environ.get("CUDA_VISIBLE_DEVICES"))
histogram = ROOT.TH1D("check", "VS Code ATLAS check", 10, 0, 10)
histogram.Fill(4.0)  # Put a breakpoint here.
print("Entries:", histogram.GetEntries())
assert histogram.GetEntries() == 1
```

Use **Run Python File in Terminal** from the editor's Run button. Then put a breakpoint on `histogram.Fill(4.0)` and run **Python Debugger: Debug Python File**, or press **F5** and choose the Python debugger. Confirm that execution stops at the breakpoint and finishes with one histogram entry. Also test an import from your own analysis package if you have one.

For a reusable F5 configuration, save this as `.vscode/launch.json` in the project ([download](../examples/vscode/launch.json)):

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "ATLAS: current Python file",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

This tests Python debugging. Stepping into compiled C++ libraries requires a separate C++ debugger configuration and suitable debug symbols.

### Notebooks and the Python Interactive window

Install **Jupyter** and **Jupyter Notebook Renderers** on the remote target. Open a notebook and use the top-right **Select Kernel** menu to choose the same ATLAS Python environment. Kernel selection is separate from **Python: Select Interpreter**. For a `.py` file with `# %%` cells, select the corresponding kernel in the Python Interactive window too.

The chosen Python must have a compatible `ipykernel`:

```bash
python -c 'import ipykernel; print(ipykernel.__version__)'
```

If that fails, arrange a writable, compatible kernel environment for that release before proceeding; do not install packages into read-only CVMFS or replace the release's ROOT/Python stack indiscriminately. Run the contents of `check_atlas.py` in a notebook cell to confirm that the **kernel**, not only a terminal, is using EL9 and ATLAS.

### Alternative: connect only the notebook kernel {#remote-jupyter}

If you only need notebooks, a **local VS Code window** can connect to a **Jupyter server started inside EL9**. Allocate a compute node and enter the configured container as above. This requires a working `jupyter` and `ipykernel` in that environment. After `asetup`, start:

```bash
jupyter lab --no-browser --ip=127.0.0.1 --port=8888
```

Keep its authentication enabled. In a **local terminal**, forward that port through the allocated node, using the actual hostname:

```bash
ssh -N -L 8888:127.0.0.1:8888 cpu001.unity.rc.umass.edu
```

In a **local VS Code window**, install Microsoft's **Jupyter** extension locally and open your notebook. Choose **Select Kernel → Select Another Kernel… → Existing Jupyter Server**, and enter the authenticated `http://127.0.0.1:8888/...` URL printed by Jupyter, including its token. If Jupyter selected another port, forward that actual port. This explicit local-window arrangement makes the local port forwarding unambiguous. The notebook file is opened and saved locally; code executes remotely, and input/output paths in that code refer to Unity storage. Keep both the Jupyter process and SSH forward alive. This provides notebook/cell execution, but does not move ordinary Python Run/F5 or language services into EL9.

## End a session and troubleshoot

Close the remote VS Code connection when finished, stop any tunnel/Jupyter process, and release the allocation by exiting its original shell or using `scancel 123456` with the correct job ID. Closing VS Code alone does not necessarily cancel the allocation.

When changing ATLAS releases, stop the previous backend and reconnect after setting up the new environment. For SSH, **Remote-SSH: Kill VS Code Server on Host…** is available; refresh the allocation configuration, hostname, and dedicated server directory as needed. For tunnels, stop the old foreground process and use a fresh session directory/name. Running `asetup` only in an already open terminal does not reconfigure the other VS Code processes.

| Symptom | Check |
| --- | --- |
| Compute-node SSH is rejected | The allocation must still be running, and the hostname, username, key, and `ProxyJump` must match it. |
| Terminal is EL9 but Run/F5 cannot import ROOT | Method A changes only the terminal. With B/C, check the selected interpreter and whether an older backend or startup file replaced the environment. |
| RemoteCommand bootstrap hangs or fails | Test the SSH alias in a terminal, inspect Remote - SSH output, and check that startup files print no extra stdout. Use the supplied stdin-preserving launcher. |
| Launcher rejects the saved job | Recreate the configuration for the current node/job; the CPU prototype expects exactly one running job of yours on that node. |
| Reconnect reaches an old environment | Stop the old backend and use the allocation-specific server/state paths. |
| Notebook import fails while Run works | Select the notebook kernel separately; check its Python path and compatible `ipykernel`. |
| Tunnel cannot sign in or connect | Check the device-login identity, outbound service access, and that the allocation and foreground CLI are still alive. |
| GPU command or framework fails | Use `--nv` and the original allocated GPU shell. Confirm Slurm's device selection with the intended framework; `nvidia-smi` alone does not validate framework compatibility or assigned-device mapping. |

For the first Unity validation, record the exact release, node, container image, and VS Code version. Test **Run**, **F5**, **a notebook cell**, and **disconnect/reconnect**. For GPU work, also run a small operation in the intended CUDA framework and confirm it uses the Slurm-assigned device. This distinguishes a working terminal from a working integrated development environment.

## References

- Unity: [SSH configuration](https://docs.unity.rc.umass.edu/documentation/connecting/ssh/), [VS Code](https://docs.unity.rc.umass.edu/documentation/connecting/vscode/), [interactive jobs](https://docs.unity.rc.umass.edu/documentation/jobs/salloc/), and [FAQ](https://docs.unity.rc.umass.edu/documentation/help/faq/).
- ATLAS: [VS Code remote usage with SSH](https://atlas-software.docs.cern.ch/athena/ide/ssh/) and [Python in VS Code](https://atlas-software.docs.cern.ch/athena/ide/python/).
- Microsoft: [Remote SSH](https://code.visualstudio.com/docs/remote/ssh), [Remote Tunnels](https://code.visualstudio.com/docs/remote/tunnels), [Python environments](https://code.visualstudio.com/docs/python/environments), [Python debugging](https://code.visualstudio.com/docs/python/debugging), and [Jupyter kernel management](https://code.visualstudio.com/docs/datascience/jupyter-kernel-management).
- Microsoft implementation details: [CLI arguments](https://github.com/microsoft/vscode/blob/main/cli/src/commands/args.rs), [CLI state/cache](https://github.com/microsoft/vscode/blob/main/cli/src/state.rs), and [server startup/reuse](https://github.com/microsoft/vscode/blob/main/cli/src/tunnels/code_server.rs).
- DCCN: [VS Code on an HPC cluster](https://hpc.dccn.nl/docs/cluster_howto/ide-vscode.html), including a tunnel launched inside a Singularity container.
- Slurm: [SSH adoption into a job](https://slurm.schedmd.com/pam_slurm_adopt.html) and [GPU resource management](https://slurm.schedmd.com/gres.html).

Reviewed 8 November 2026. The canonical ATLAS pages were inaccessible from the research environment; their CERN-hosted mirrors were used to check the [SSH](https://shahzad.web.cern.ch/shahzad/atlas-software-docs/athena/ide/ssh/) and [Python](https://shahzad.web.cern.ch/shahzad/atlas-software-docs/athena/ide/python/) guidance. The Unity adaptations remain to be tested as noted above.
