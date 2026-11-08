Use a Slurm allocation for your work, then start an EL9 container on the allocated compute node. Inside it, ATLAS software is available through CVMFS without a local installation.

::: {.callout}
**Before you begin:** you need a Unity account, access to a group work directory, and a Bash shell. CVMFS must be accessible on the **compute node**, not just the login node.
:::

## 1. Connect to Unity {#connect}

From your own computer, connect using your Unity username:

```bash
# Your computer — replace YOUR_USERNAME with your Unity username.
ssh YOUR_USERNAME@login.unityhpc.org
```

Follow Unity's [SSH guide](https://docs.unity.rc.umass.edu/documentation/connecting/ssh/) for account and SSH-key setup. Use the login node to prepare and submit work; run builds, event processing, and training on allocated compute nodes.

## 2. Create your working directories once {#directories}

On the **Unity login node**, set `USER_PI` to your PI's existing Unity directory name, for example `rclsa_umass_edu`. Substitute your own PI directory for `YOUR_PI`. `$USER` is already your Unity username after logging in, so leave it as a variable.

```bash
# Unity login node — replace YOUR_PI, for example with rclsa_umass_edu.
export USER_PI=YOUR_PI
mkdir -p "/work/${USER_PI}/${USER}"
mkdir -p "/project/${USER_PI}/${USER}"

# The examples throughout this manual use this analysis subdirectory.
mkdir -p "/work/${USER_PI}/${USER}/atlas"
```

**Create these directories only once**, not for every allocation or container. `mkdir -p` also succeeds if they already exist. Your PI's storage allocation must already be provisioned and accessible; these commands create your own subdirectories, not a new storage allocation.

Add your edited `export USER_PI=...` line to your existing `~/.bashrc` so the choice persists across sessions. The complete [shell configuration below](#bashrc) includes this line and defines `ATLAS_WORKDIR="/work/${USER_PI}/${USER}/atlas"`; keep a single definition of each when merging it. Directory creation stays outside `.bashrc`.

`ATLAS_WORKDIR` is your common analysis work area. Later chapters use `"$ATLAS_WORKDIR/PROJECT_NAME"` for an individual analysis checkout; replace `PROJECT_NAME` with that repository's directory name.

Throughout the manual, `/work/${USER_PI}/${USER}` is your personal work area and `/project/${USER_PI}/${USER}` is your personal area in your PI's project allocation. Use `/work` or Unity's [scratch service](https://docs.unity.rc.umass.edu/documentation/managing-files/hpc-workspace/) for active job I/O. Consult the [storage guide](https://docs.unity.rc.umass.edu/documentation/cluster_specs/storage/) for quotas and retention.

## 3. Request compute resources {#allocate}

Choose **one** of the following commands on the login node. Adjust the resource request to your workload.

### CPU session

```bash
# Unity login node
salloc --partition=cpu --nodes=1 --ntasks=1 \
       --cpus-per-task=4 --mem=16G --time=02:00:00
```

### GPU session

```bash
# Unity login node — alternative to the CPU request
salloc --partition=gpu --nodes=1 --ntasks=1 --gpus=1 \
       --cpus-per-task=4 --mem=16G --time=02:00:00
```

| Option | Meaning in these examples |
| --- | --- |
| `--nodes=1 --ntasks=1` | One node and one task. |
| `--cpus-per-task=4` | Four CPU cores for that task. Configure your application's threads accordingly. |
| `--mem=16G` | 16 GB of host memory for the node allocation; this is not GPU memory. |
| `--time=02:00:00` | A two-hour wall-time limit. |
| `--gpus=1` | One GPU, only in the GPU example. |

Unity's documented `salloc` workflow opens a shell on the compute node once resources are available. Confirm your location:

```bash
# After the allocation is granted
hostname -f
printf 'Job: %s\nNodes: %s\n' "$SLURM_JOB_ID" "$SLURM_JOB_NODELIST"
uname -m
```

The hostname should be a compute node in your allocation. If you are still on a login node with an active allocation, use `srun --pty bash -l` to start a shell on the allocated node. Do not run a second `salloc` inside the first one.

This guide targets **x86_64** nodes. Containers do not translate CPU architectures; ARM and POWER partitions need compatible software and images. `gpu-preempt` is an alternative when interruption is acceptable. Consult the current [partition list](https://docs.unity.rc.umass.edu/documentation/cluster_specs/partitions/) and [GPU guide](https://docs.unity.rc.umass.edu/documentation/tools/gpus/) before choosing constraints or preemptible resources.

## 4. Prepare the host environment {#prepare-host}

Run the following in the **Ubuntu compute-node shell**, before entering a container:

```bash
module load apptainer/latest
apptainer --version

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
alias setupATLAS='source ${ATLAS_LOCAL_ROOT_BASE}/user/atlasLocalSetup.sh'

# Forward the directory variables explicitly into Apptainer.
export APPTAINERENV_USER_PI="$USER_PI"
export APPTAINERENV_USER="$USER"

ls -l "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
```

The last command must find the setup script. Stop here if it fails: an empty `/cvmfs` directory alone does not establish that the ATLAS repository is available. Report the compute-node hostname and the missing path to Unity support. The first access to a CVMFS path may take longer while content is fetched.

Start from a clean host shell. Deactivate any Conda or Python virtual environment and avoid loading Ubuntu ROOT, Python, or compiler modules for use inside the EL9 environment. Load the Apptainer runtime on the host; select analysis tools inside the container.

### Choose a work directory

Use the analysis subdirectory you created in the one-time setup:

```bash
# Ubuntu compute node
export ATLAS_WORKDIR="/work/${USER_PI}/${USER}/atlas"
export APPTAINERENV_ATLAS_WORKDIR="$ATLAS_WORKDIR"
cd "$ATLAS_WORKDIR"
pwd -P
```

Keep shell configuration in your home directory. Subsequent chapters assume the [shell configuration below](#bashrc) is installed, so they reuse `ATLAS_WORKDIR` and the allocation/container shortcuts.

## 5. Enter the EL9 container {#container}

For a CPU session, run:

```bash
# Ubuntu compute node, in your analysis directory
setupATLAS -c el9
```

`-c el9` selects the ATLAS EL9 environment. Unity exposes `/work` inside the container without `-m /work`, so no explicit mount is needed for the standard workflow. File permissions still apply.

Use `-m` only when a directory you need is **not already visible** inside the container. For example, if `/scratch` is missing, leave the container and relaunch with `setupATLAS -c el9 -m /scratch`. Check the paths you need after entering; automatic mounts can depend on the launcher and site configuration. `setupATLAS -c -h` describes additional mount options.

The launcher initializes the ATLAS user interface in the container. Check it before selecting a release:

```bash
# Inside the EL9 container
cat /etc/os-release
uname -m
pwd
type lsetup
type asetup
ls /cvmfs/atlas.cern.ch/repo
ls /work
printf 'PI: %s\nUser: %s\n' "$USER_PI" "$USER"
cd "$ATLAS_WORKDIR"
```

Expect an EL9 distribution and `x86_64`. A container shares the host kernel, so `uname -r` is **not** a test of its Linux distribution. The launcher may initially map the working directory to `/srv` and use a different home path. The explicit `cd` returns to the shared analysis directory. The `APPTAINERENV_` exports above preserve `USER_PI`, `USER`, and `ATLAS_WORKDIR` inside Apptainer; other host variables need not be preserved. If you need project files, also check that `/project/${USER_PI}/${USER}` is visible, using the mount guidance above if needed.

If `lsetup` is unavailable despite a successful container launch, initialize the interface explicitly **inside** that container:

```bash
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
```

::: {.callout}
**Two separate choices.** The container selects the operating-system environment. `asetup` selects an ATLAS software release. Entering EL9 does not by itself load AnalysisBase, AthAnalysis, or Athena.
:::

## 6. Load analysis software {#software}

Choose the environment needed by your analysis. Use a fresh container session when switching between unrelated software stacks.

### A standalone ROOT check

In an EL9 session with no analysis release loaded:

```bash
lsetup root
root-config --version
python -c 'import ROOT; print(ROOT.gROOT.GetVersion())'
```

This checks a basic ROOT/PyROOT environment. For reproducible work, select an explicit tool version using the choices shown by `lsetup "root --help"`, and record it with your analysis.

### AnalysisBase, AthAnalysis, or Athena

For an analysis release, begin in a **fresh EL9 session** and select the exact project and version required by your analysis, following the ATLAS [release setup guide](https://atlas-software.docs.cern.ch/analysis/analysis_tutorial/AnalysisSWTutorial/release_setup/). Throughout this manual, `ATLAS_RELEASE` means the complete `project,version` pair: for example, `AnalysisBase` followed by a comma and your exact release number. Enter that pair at the prompt:

```bash
# Inside a fresh EL9 container, in your analysis directory
read -r -p 'ATLAS project,version: ' ATLAS_RELEASE
if [[ "$ATLAS_RELEASE" == *,* ]]; then
    asetup "$ATLAS_RELEASE"
else
    echo 'Enter a project and exact version, separated by a comma.'
fi
```

Use `AthAnalysis` or `Athena` in place of `AnalysisBase` when that is what your workflow requires. Check the setup output for a successful release selection and an EL9-compatible platform. Use an exact version rather than `latest`; the analysis determines the supported release. `ATLAS_RELEASE` is a session variable, so set it again when starting a new session or submitting from a different shell.

After a successful setup:

```bash
printf 'Project: %s\nVersion: %s\nPlatform: %s\n' \
       "$AtlasProject" "$AtlasVersion" "$BINARY_TAG"
command -v python
root-config --version
python -c 'import ROOT; print(ROOT.gROOT.GetVersion())'
```

Use the ROOT and Python supplied by the release. Keep standalone `lsetup root` and release setup in separate sessions. Record the project, version, platform, and container information with your code; record the resolved image from the launcher output if you need to reproduce the precise container as well.

## 7. Enable GPU access {#gpu}

For an **NVIDIA GPU allocation**, use this launch sequence in place of the CPU container command. First check the host:

```bash
# Ubuntu GPU compute node, after salloc and host preparation
nvidia-smi
printf 'CUDA_VISIBLE_DEVICES=%s\n' "${CUDA_VISIBLE_DEVICES:-<unset>}"
```

Pass **`--nv` explicitly to the container runtime through `ALRB_CONT_CMDOPTS`**. This exposes the host's NVIDIA utilities and driver libraries inside EL9. The following sequence preserves any existing container options and forwards Slurm's device selection:

```bash
# Ubuntu GPU compute node; module load apptainer/latest was done above.
(
    export ALRB_CONT_CMDOPTS="${ALRB_CONT_CMDOPTS:+$ALRB_CONT_CMDOPTS }--nv"
    if [[ ${CUDA_VISIBLE_DEVICES+x} ]]; then
        export APPTAINERENV_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
    fi
    if [[ ${CUDA_DEVICE_ORDER+x} ]]; then
        export APPTAINERENV_CUDA_DEVICE_ORDER="$CUDA_DEVICE_ORDER"
    fi
    setupATLAS -c el9
)
```

The enclosing parentheses run the launch in a subshell. When you exit the container, these exports disappear and the host shell's previous container options are preserved. Set these options **before starting the container**; setting them inside an already running container cannot add the missing GPU mounts.

Then check **inside** the container:

```bash
command -v nvidia-smi
nvidia-smi
printf 'CUDA_VISIBLE_DEVICES=%s\n' "${CUDA_VISIBLE_DEVICES:-<unset>}"
```

Check the launcher's output for `apptainer ... --nv ...`. This guide passes the option explicitly through the ATLAS launcher; `APPTAINER_NV=true` is Apptainer's environment-variable equivalent.

If `nvidia-smi` is still missing, try `/usr/bin/nvidia-smi` inside the container. If the full path works but the bare command does not, inspect `PATH`. If the file is absent, check the container launch line and any mount warnings; changing `PATH` cannot expose an unmounted executable. Confirm that `nvidia-smi` works on the same GPU node outside the container first. See the [Apptainer GPU documentation](https://apptainer.org/docs/user/latest/gpu.html) for runtime details.

GPU visibility does not install a CUDA-enabled analysis framework, or make ordinary ATLAS code use the GPU. Verify device visibility and compatibility with the framework you intend to use. Do not override Slurm's device selection or set it to `all`; `nvidia-smi` may enumerate more devices than your application is assigned.

The next section puts this launch sequence in a reusable `.bashrc` function so you only need to type `atlas_gpu` on the allocated node.

## 8. Save your shell configuration {#bashrc}

Add the following to **your existing** `~/.bashrc` on Unity, replacing `YOUR_PI` with your actual PI directory (for example, `rclsa_umass_edu`). If you already added `USER_PI` above, keep just one edited definition. These lines save the directory settings and define commands; they do not create directories, allocate resources, or start software at login. **The remaining chapters assume this configuration is in place.** The same snippet is available as [atlas-bashrc.sh](../examples/atlas-bashrc.sh).

```bash
# Add to your existing ~/.bashrc on Unity; do not replace that file.
# This defines shortcuts only. It does not start a container or allocate a job.
# Replace YOUR_PI with your Unity PI directory, for example rclsa_umass_edu.
export USER_PI=YOUR_PI
export ATLAS_WORKDIR="/work/${USER_PI}/${USER}/atlas"
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase

# Pixi and personal tools installed with pixi global (see the Using Pixi chapter).
export PATH="$HOME/.pixi/bin:$PATH"

# Keep these path variables available even when Apptainer cleans the environment.
export APPTAINERENV_USER_PI="$USER_PI"
export APPTAINERENV_USER="$USER"
export APPTAINERENV_ATLAS_WORKDIR="$ATLAS_WORKDIR"

if [[ $- == *i* ]]; then
    alias setupATLAS='source ${ATLAS_LOCAL_ROOT_BASE}/user/atlasLocalSetup.sh'
    alias unity_cpu='salloc --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G --time=02:00:00'
    alias unity_gpu='salloc --partition=gpu --nodes=1 --ntasks=1 --gpus=1 --cpus-per-task=4 --mem=16G --time=02:00:00'

    # Run on an allocated NVIDIA GPU node. The subshell keeps these
    # container options local to this invocation.
    atlas_gpu() (
        module load apptainer/latest || return "$?"
        export ALRB_CONT_CMDOPTS="${ALRB_CONT_CMDOPTS:+$ALRB_CONT_CMDOPTS }--nv"
        if [[ ${CUDA_VISIBLE_DEVICES+x} ]]; then
            export APPTAINERENV_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
        fi
        if [[ ${CUDA_DEVICE_ORDER+x} ]]; then
            export APPTAINERENV_CUDA_DEVICE_ORDER="$CUDA_DEVICE_ORDER"
        fi
        source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" -c el9 "$@"
    )
fi
```

The `PATH` line makes Pixi and its personal command-line tools available after you follow [Using Pixi](../using-pixi/#installation). It is safe to include before installing Pixi.

Reload it in the **host shell** with `source ~/.bashrc`. The GPU workflow is then:

```bash
# Unity login node: request a GPU allocation.
unity_gpu

# After allocation, on the Ubuntu GPU compute node:
# choose your work directory, then start the EL9 container.
cd "$ATLAS_WORKDIR"
atlas_gpu
```

`ATLAS_WORKDIR` is derived from your saved `USER_PI` and Unity `$USER`. If your allocated shell has not loaded the settings or function yet, run `source ~/.bashrc` there. The `APPTAINERENV_` exports preserve the directory variables when the container starts.

`unity_gpu` requests resources; `atlas_gpu` loads Apptainer and starts EL9 with `--nv` on the allocated node. The function preserves existing `ALRB_CONT_CMDOPTS` options, passes the current allocation's `CUDA_VISIBLE_DEVICES`, and confines the exports to its subshell. Adding the definition to `.bashrc` does not start a container at login. You can pass extra ATLAS container arguments, for example `atlas_gpu -m /another/path` if a required path is not already visible.

For CPU work, continue to use `unity_cpu`, then the host preparation and `setupATLAS -c el9` commands above.

Keep module loading and software startup inside explicitly invoked commands or functions, rather than executing them automatically when `.bashrc` is read. This avoids unexpected containers or incompatible software environments when starting new shells. Batch scripts and SSH launchers still initialize their own environment explicitly; non-interactive Bash does not normally expand aliases.

## 9. End or reconnect to a session {#sessions}

Run `exit` inside the container to return to the Ubuntu compute-node shell. Run `exit` again to leave the interactive allocation and release its resources. A new allocation requires a new container and software setup; files in your work directory remain.

For a session that survives an SSH disconnect, start `tmux new -s atlas` **on the login node before `salloc`**. Detach with **Ctrl+B**, then **D**. Reconnect to the same login node and use `tmux attach -t atlas`. Record that login hostname before starting. `tmux` does not extend the Slurm wall-time limit or prevent preemption. See Unity's [interactive-job guidance](https://docs.unity.rc.umass.edu/documentation/jobs/).

## Troubleshooting {#troubleshooting}

| Symptom | What to check |
| --- | --- |
| `setupATLAS: command not found` | Define the export and alias in the current Bash shell, or source the setup script explicitly. |
| Missing `atlasLocalSetup.sh` | Test its full CVMFS path on the allocated compute node; ask Unity support if unavailable. |
| `apptainer: command not found` | Load `apptainer/latest` on the host. Use `module avail apptainer` if the module name changes. |
| Container fails with namespace or mount errors | Save the launcher output and hostname for support; node/runtime configuration may need adjustment. |
| Work files disappear inside the container | Add the correct host path with `-m`, including a symlink's real target; verify with `pwd -P` before launch. |
| Container still reports Ubuntu | Check `/etc/os-release`; the container may have failed to start, leaving you in the host shell. |
| ROOT/Python errors after setup | Try a fresh container, choose one software stack, and check the release's platform. |
| `nvidia-smi: command not found` inside EL9 | Confirm it works on the host, restart with `--nv` through `ALRB_CONT_CMDOPTS`, and check launcher warnings. Test `/usr/bin/nvidia-smi` to distinguish a missing mount from a `PATH` issue. |
| GPU works on host but not in container | Confirm an NVIDIA allocation, `--nv` in the launch command, and preservation of Slurm's device selection. |
| Allocation is pending | Inspect `squeue -u "$USER"` on the host; reduce an unnecessarily large request or consult current partition availability. |

## References {#references}

- [ATLAS Software Documentation](https://atlas-software.docs.cern.ch/): [environment prerequisites](https://atlas-software.docs.cern.ch/athena/developers/tutorial/prerequisites/) and [user-interface setup](https://atlas-software.docs.cern.ch/analysis/analysis_tutorial/basicSetup/setup_ui/).
- [Unity documentation](https://docs.unity.rc.umass.edu/documentation/): [interactive CLI jobs](https://docs.unity.rc.umass.edu/documentation/jobs/salloc/), [container support](https://docs.unity.rc.umass.edu/documentation/help/faq/), [partitions](https://docs.unity.rc.umass.edu/documentation/cluster_specs/partitions/), and [storage](https://docs.unity.rc.umass.edu/documentation/cluster_specs/storage/).
- [US ATLAS Analysis Facilities: Apptainer usage](https://usatlas.github.io/af-docs/containers/apptainer/usage/) and [benchmarking examples](https://github.com/usatlas/af-benchmarking/blob/main/README.md) using `ALRB_CONT_CMDOPTS`.
- [Apptainer GPU support](https://apptainer.org/docs/user/latest/gpu.html) and [environment-variable reference](https://apptainer.org/docs/user/latest/appendix.html).

**Next:** [Submitting jobs with Slurm](../submitting-jobs/) recreates this environment automatically on a batch worker.

