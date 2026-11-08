Run JupyterLab from your own terminal session on a Unity compute node, then connect from a browser on your computer through an SSH tunnel. Your project chooses the Pixi packages; you choose the Slurm resources and whether to run inside EL9. Notebooks, data access, and computation stay on Unity.

This chapter assumes you have completed [Setting up the environment](../setting-up-environment/), including the one-time directories and [`.bashrc` configuration](../setting-up-environment/#bashrc), and [installed Pixi](../using-pixi/#installation). It reuses `USER_PI`, Unity `$USER`, `ATLAS_WORKDIR`, and the allocation/container helpers.

## 1. Prepare the project and your SSH connection {#prepare}

Use an existing project whose Pixi environment includes **`jupyterlab`, `ipykernel`, and the analysis packages** you need. For example, a HEP project might supply Uproot, Awkward Array, Hist, and plotting packages. The examples below use the project's default environment. See [Using Pixi](../using-pixi/#projects) for installing a supplied manifest, or the [Carpentries introduction](https://carpentries-incubator.github.io/pixi-introduction/) for creating or changing one.

JupyterLab supplies the interface and server; the **kernel** is the Python process that executes notebook cells. Both will run in the project's Pixi environment in this recipe. A global Jupyter installation is not needed.

On your **local computer**, use the SSH configuration from [Using VS Code](../using-vscode/#configure-your-local-computer). If you have not configured it yet, merge the following into `~/.ssh/config` on Linux/macOS or `%USERPROFILE%\.ssh\config` on Windows. Replace `YOUR_USERNAME` and the private-key path with your Unity account and key; do not duplicate entries already present.

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

The second entry reaches a compute node through the login service. It uses your literal Unity username, which may differ from your laptop's `$USER`. Use an ordinary compute-node connection for this chapter, without the VS Code container `RemoteCommand` alias.

In your first local terminal, connect:

```bash
ssh unity
```

If Windows OpenSSH reports `Corrupted MAC on input`, Unity's [SSH guide](https://docs.unity.rc.umass.edu/documentation/connecting/ssh/) documents adding `MACs hmac-sha2-512-etm@openssh.com` to the affected SSH host entries.

## 2. Allocate a compute node {#allocation}

On the **Unity login node**, record the login hostname, then start `tmux` before requesting resources. This lets the allocation and Jupyter process survive an SSH disconnection:

```bash
hostname -f
tmux new -s atlas-jupyter

# Inside tmux, on the login node:
unity_cpu
```

The CPU helper requests four CPUs, 16 GB of memory, and two hours. Adjust the allocation to your workload using the [environment chapter](../setting-up-environment/#allocate). For a GPU session, use `unity_gpu` **instead of** `unity_cpu`.

When the allocation starts, you should be in the **Ubuntu compute-node shell**. Use the [location checks in the environment chapter](../setting-up-environment/#allocate) if the shell remains on a login node. Record both values below; the compute hostname is the destination for your later SSH tunnel, while the job ID identifies the allocation:

```bash
hostname -f
echo "$SLURM_JOB_ID"
```

If the new shell has not loaded your directory settings or helpers, run `source ~/.bashrc` there. Start Jupyter in this allocated shell, not on the login node.

## 3. Choose Ubuntu or EL9 {#runtime}

For a self-contained Pixi analysis that supports Unity's Ubuntu hosts, you can remain in the compute-node shell. If your project requires EL9, enter the container **before installing or starting its environment**:

```bash
# Ubuntu compute node, for a CPU session requiring EL9:
module load apptainer/latest
cd "$ATLAS_WORKDIR"
setupATLAS -c el9
```

For an allocated NVIDIA GPU node, use `cd "$ATLAS_WORKDIR"` followed by `atlas_gpu` instead. That helper enables the GPU passthrough described in the environment chapter. The Pixi environment must also contain a compatible GPU framework; reserving a GPU does not make ordinary notebook code use it.

Inside EL9, check `cat /etc/os-release`. This workflow uses Apptainer's normal shared host networking, so the SSH tunnel can reach Jupyter on the compute node's loopback address. Do not add a separate network namespace such as `--net` to this recipe.

**Keep an independent Pixi analysis separate from `asetup`**, as described in [Using Pixi alongside ATLAS](../using-pixi/#atlas). Start with a fresh shell/container before loading an ATLAS release. A Pixi Python environment does not automatically acquire the release's PyROOT or Athena bindings, and inherited ATLAS Python/library paths can conflict with its packages. If your notebook needs those bindings, it needs a compatible ATLAS kernel setup; see the [ATLAS notebook checks in Using VS Code](../using-vscode/#notebooks-and-the-python-interactive-window).

## 4. Install the environment and start JupyterLab {#start}

In the chosen **compute-node environment** (Ubuntu or EL9), enter the existing project. Replace `PROJECT_NAME` with its directory name:

```bash
cd "$ATLAS_WORKDIR/PROJECT_NAME"

# Restore the user-tool path if the container reset PATH.
export PATH="$HOME/.pixi/bin:$PATH"
pixi install
pixi run python -c 'import sys, jupyterlab, ipykernel; print(sys.executable)'
```

Keep the printed Python path for the notebook check below. If an import fails, the project's environment needs the missing dependency. Update the manifest through the project's normal workflow; do not install into an unrelated Python. For a project with a supplied lock file, you can use `pixi install --locked` as explained in [Using Pixi](../using-pixi/#projects).

Give this environment's kernel a clear name. Run this once after installing the environment, and repeat if you recreate or move it:

```bash
pixi run python -m ipykernel install --sys-prefix \
  --name unity-hep --display-name "Python (HEP Pixi)"
```

`--sys-prefix` places the kernel definition inside this Pixi environment, where this JupyterLab server can find it. It does not register a container-dependent interpreter for every other Jupyter server in your account. The definition records the interpreter path, so keep the project in its current location during the session.

Now start the server in the foreground:

```bash
pixi run jupyter lab --no-browser --ip=127.0.0.1 --port=8888 \
  --ServerApp.port_retries=0
```

The server listens only on the compute node's loopback interface. `port_retries=0` makes it stop if port 8888 is occupied, instead of silently choosing another port. In that case, select another port, such as 8890, here **and in the remote-port position of the tunnel below**.

Keep authentication enabled. With Jupyter's default token authentication, the terminal prints an HTTP URL containing a private token. Keep that terminal running; do not copy the token into a repository or share it. If you previously configured a Jupyter password, use that password when prompted instead.

## 5. Connect from your browser {#connect}

Open a **second terminal on your local computer**. Replace `COMPUTE_NODE` with the full compute hostname recorded in step 2, for example `cpu001.unity.rc.umass.edu`:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8888:127.0.0.1:8888 COMPUTE_NODE
```

This command uses the `ProxyJump` configuration above. It forwards your computer's port 8888 to port 8888 on the allocated node's loopback interface. The SSH destination must be the **compute node**; forwarding to the login node's loopback would reach the wrong machine. A quiet terminal is normal: leave the tunnel running.

Open the `http://127.0.0.1:8888/lab?token=...` URL in your local browser, substituting the actual token printed by Jupyter. Use its HTTP URL, not the `file:///...` shortcut, which refers to a file on Unity. The SSH connection carries the browser traffic to the server.

If port 8888 is already used on your **local computer**, use a different local port while retaining the server's remote port:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8889:127.0.0.1:8888 COMPUTE_NODE
```

Then open `http://127.0.0.1:8889/lab?token=...` with the same token. In `-L`, the first port is local and the last port is on the compute node.

## 6. Select and check the notebook kernel {#kernel}

In JupyterLab, open or create a notebook and select **Python (HEP Pixi)** from the kernel menu. Check this even for an existing notebook: it may remember a different kernel.

Run the following cell:

```python
import sys
from pathlib import Path

print("Python:", sys.executable)
print("Working directory:", Path.cwd())
```

The Python path should match the one printed by `pixi run python` in step 4. Test the analysis packages your project actually includes, for example:

```python
import uproot
import awkward as ak
import hist

print("Uproot:", uproot.__version__)
print("Awkward:", ak.__version__)
print("Hist:", hist.__version__)
```

The selected kernel has access to the packages installed in that Pixi environment and the files visible to its Unity process. Notebook paths refer to Unity storage, not your laptop. JupyterLab's file browser starts in the project directory; notebooks saved there are saved on Unity. Normal filesystem permissions and container mounts still apply. For a GPU project, also run its framework's device check in a cell.

## 7. Disconnect, reconnect, and finish {#sessions}

Save the notebook before disconnecting. In the first terminal, detach from `tmux` with **Ctrl+B**, then **D**. You can then close the SSH connection and stop the local forwarding command with **Ctrl+C**. The server and kernel can continue while their allocation is running. Closing a browser tab alone does not stop them or release resources.

To return, reconnect to Unity and use `ssh loginX` to reach the same login node you recorded before starting `tmux`, if necessary. Then run:

```bash
tmux attach -t atlas-jupyter
```

Recreate the local SSH tunnel and reopen the authenticated URL. If the same Jupyter server and kernel are still running, their in-memory state remains available. Once the Slurm time limit is reached, the job is cancelled, or the node fails, that state is lost; a new allocation requires a new server and tunnel destination. Saved notebooks and files remain, but saved cell output is not a checkpoint of Python variables.

When finished, save your work, stop Jupyter with **Ctrl+C** in its terminal and confirm shutdown if prompted. Exit the container if you entered one, then exit the original allocated compute shell to release the allocation. Stop the local SSH tunnel too. From a login shell you can check remaining jobs with `squeue -u "$USER"`.

## Troubleshooting {#troubleshooting}

| Symptom | What to check |
| --- | --- |
| `jupyter` or `ipykernel` is missing | Both must be in this project's Pixi environment; check imports through `pixi run python`. |
| The server reports its port is occupied | Select a different server port and update the tunnel's remote port. Keep the fixed-port behavior. |
| SSH reports `Address already in use` | Change the tunnel's local port and the browser URL, as in the 8889 example. |
| Compute-node SSH fails | Check the live allocation, full compute hostname, Unity username/key, and `ProxyJump` configuration. |
| Browser connection is refused | Keep both Jupyter and the local tunnel running; check that the tunnel targets the correct node and server port. |
| Browser asks for authentication | Use the current server's token or configured password. A restarted server may have a new token. |
| Imports work in a terminal but fail in the notebook | Select **Python (HEP Pixi)** and compare `sys.executable`. Repeat kernel registration if the environment was recreated or moved. |
| A package was added but the notebook still uses the old state | Stop/restart the kernel after updating the environment; rerun the notebook cells. |
| ATLAS bindings fail in Pixi Python | Follow a project-supported ATLAS kernel setup; EL9 alone does not make independent Python environments interchangeable. |

## References {#references}

- Unity: [SSH](https://docs.unity.rc.umass.edu/documentation/connecting/ssh/), [compute-node SSH configuration](https://docs.unity.rc.umass.edu/documentation/connecting/vscode/), and [interactive jobs and tmux](https://docs.unity.rc.umass.edu/documentation/jobs/).
- Pixi: [JupyterLab integration](https://pixi.prefix.dev/latest/integration/editor/jupyterlab/) and [running commands](https://pixi.prefix.dev/latest/reference/cli/pixi/run/).
- Jupyter: [authentication and token URLs](https://jupyter-server.readthedocs.io/en/latest/operators/security.html), [server options](https://jupyter-server.readthedocs.io/en/latest/other/full-config.html), and [kernel troubleshooting](https://jupyter-notebook.readthedocs.io/en/latest/troubleshooting.html).
- IPython: [kernel registration](https://ipython.readthedocs.io/en/stable/install/kernel_install.html).
- OpenSSH: [`ssh` port forwarding](https://man.openbsd.org/ssh.1).
- Apptainer: [network namespaces](https://apptainer.org/docs/user/latest/networking.html).

**Next:** [Codex Agents](../codex-agents/) adds an agent with ATLAS software and authenticated dataset tools.
