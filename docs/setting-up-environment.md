Use a Slurm allocation for your work, then start an EL9 container on the allocated compute node. Inside it, ATLAS software is available through CVMFS without a local installation.

::: {.callout}
**Before you begin:** you need a Unity account, access to a group work directory, and a Bash shell. CVMFS must be accessible on the **compute node**, not just the login node. Rafael has tested this interactive recipe successfully on Unity.
:::

## 1. Connect to Unity {#connect}

From your own computer, connect using your Unity username:

```bash
# Your computer — replace YOUR_UNITY_USERNAME.
ssh YOUR_UNITY_USERNAME@login.unityhpc.org
```

Follow Unity's [SSH guide](https://docs.unity.rc.umass.edu/documentation/connecting/ssh/) for account and SSH-key setup. Use the login node to prepare and submit work; run builds, event processing, and training on allocated compute nodes.

## 2. Request compute resources {#allocate}

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

## 3. Prepare the host environment {#prepare-host}

Run the following in the **Ubuntu compute-node shell**, before entering a container:

```bash
module load apptainer/latest
apptainer --version

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
alias setupATLAS='source ${ATLAS_LOCAL_ROOT_BASE}/user/atlasLocalSetup.sh'

ls -l "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
```

The last command must find the setup script. Stop here if it fails: an empty `/cvmfs` directory alone does not establish that the ATLAS repository is available. Report the compute-node hostname and the missing path to Unity support. The first access to a CVMFS path may take longer while content is fetched.

Start from a clean host shell. Deactivate any Conda or Python virtual environment and avoid loading Ubuntu ROOT, Python, or compiler modules for use inside the EL9 environment. Load the Apptainer runtime on the host; select analysis tools inside the container.

### Choose a work directory

Replace `pi_YOUR_PI` with your actual Unity group directory. Do not run the placeholder unchanged.

```bash
# Ubuntu compute node — edit the group directory first
export ATLAS_WORKDIR="/work/pi_YOUR_PI/$USER/atlas"
mkdir -p "$ATLAS_WORKDIR"
cd "$ATLAS_WORKDIR"
pwd -P
```

Use `/work` or a workspace allocated through Unity's [scratch service](https://docs.unity.rc.umass.edu/documentation/managing-files/hpc-workspace/) for active job I/O. Keep shell configuration in your home directory. Consult the [storage guide](https://docs.unity.rc.umass.edu/documentation/cluster_specs/storage/) for quotas, retention, and moving data from longer-term storage.

## 4. Enter the EL9 container {#container}

For a CPU session, run:

```bash
# Ubuntu compute node, in your analysis directory
setupATLAS -c el9
```

`-c el9` selects the ATLAS EL9 environment. On the tested Unity setup, `/work` is already visible inside the container without `-m /work`, so no explicit mount is needed for the standard workflow. File permissions still apply.

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
```

Expect an EL9 distribution and `x86_64`. A container shares the host kernel, so `uname -r` is **not** a test of its Linux distribution. The launcher may map the working directory to `/srv` and use a different home path. Check `pwd` and access to your `/work/...` directory. Host variables such as `ATLAS_WORKDIR` need not be preserved.

If `lsetup` is unavailable despite a successful container launch, initialize the interface explicitly **inside** that container:

```bash
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
```

::: {.callout}
**Two separate choices.** The container selects the operating-system environment. `asetup` selects an ATLAS software release. Entering EL9 does not by itself load AnalysisBase, AthAnalysis, or Athena.
:::

## 5. Load analysis software {#software}

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

For an analysis release, begin in a **fresh EL9 session** and select the exact project and version required by your analysis, following the ATLAS [release setup guide](https://atlas-software.docs.cern.ch/analysis/analysis_tutorial/AnalysisSWTutorial/release_setup/). For example, this prompts for a version instead of silently choosing a moving default:

```bash
# Inside a fresh EL9 container, in your analysis directory
read -r -p 'AnalysisBase release required by your analysis: ' ATLAS_RELEASE
if [[ -n "$ATLAS_RELEASE" ]]; then
    asetup "AnalysisBase,${ATLAS_RELEASE}"
fi
```

Use `AthAnalysis` or `Athena` in place of `AnalysisBase` when that is what your workflow requires. Check the setup output for a successful release selection and an EL9-compatible platform. Do not guess a release number from this guide; the analysis determines the supported release.

After a successful setup:

```bash
printf 'Project: %s\nVersion: %s\nPlatform: %s\n' \
       "$AtlasProject" "$AtlasVersion" "$BINARY_TAG"
command -v python
root-config --version
python -c 'import ROOT; print(ROOT.gROOT.GetVersion())'
```

Use the ROOT and Python supplied by the release. Keep standalone `lsetup root` and release setup in separate sessions. Record the project, version, platform, and container information with your code; record the resolved image from the launcher output if you need to reproduce the precise container as well.

## 6. Enable GPU access {#gpu}

For an **NVIDIA GPU allocation**, use this launch sequence in place of the CPU container command. First check the host:

```bash
# Ubuntu GPU compute node, after salloc and host preparation
nvidia-smi
printf 'CUDA_VISIBLE_DEVICES=%s\n' "${CUDA_VISIBLE_DEVICES:-<unset>}"
```

Pass **`--nv` explicitly to the container runtime through `ALRB_CONT_CMDOPTS`**. This exposes the host's NVIDIA utilities and driver libraries inside EL9. Rafael confirmed that this launch sequence makes `nvidia-smi` work on Unity after it was missing with the earlier recipe. It preserves any existing container options and forwards Slurm's device selection:

```bash
# Ubuntu GPU compute node; module load apptainer/latest was done above.
(
    export ALRB_CONT_CMDOPTS="${ALRB_CONT_CMDOPTS:+$ALRB_CONT_CMDOPTS }--nv"
    if [[ -n ${CUDA_VISIBLE_DEVICES:-} ]]; then
        export APPTAINERENV_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
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

Check the launcher's output for `apptainer ... --nv ...`. `APPTAINER_NV=true` is Apptainer's environment-variable equivalent, but this guide uses the explicit option that was tested successfully through the ATLAS launcher on Unity. No manual `PATH` change was needed in that test.

If `nvidia-smi` is still missing, try `/usr/bin/nvidia-smi` inside the container. If the full path works but the bare command does not, inspect `PATH`. If the file is absent, check the container launch line and any mount warnings; changing `PATH` cannot expose an unmounted executable. Confirm that `nvidia-smi` works on the same GPU node outside the container first. See the [Apptainer GPU documentation](https://apptainer.org/docs/user/latest/gpu.html) for runtime details.

GPU visibility does not install a CUDA-enabled analysis framework, or make ordinary ATLAS code use the GPU. Verify device visibility and compatibility with the framework you intend to use. Do not override Slurm's device selection or set it to `all`; `nvidia-smi` may enumerate more devices than your application is assigned.

The next section puts this launch sequence in a reusable `.bashrc` function so you only need to type `atlas_gpu` on the allocated node.

## 7. Add optional shell shortcuts {#bashrc}

Add the following to **your existing** `~/.bashrc` on Unity. These lines define commands; they do not allocate resources or start software at login. The same snippet is available as [atlas-bashrc.sh](../examples/atlas-bashrc.sh).

```bash
# Add to your existing ~/.bashrc on Unity; do not replace that file.
# This defines shortcuts only. It does not start a container or allocate a job.
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase

if [[ $- == *i* ]]; then
    alias setupATLAS='source ${ATLAS_LOCAL_ROOT_BASE}/user/atlasLocalSetup.sh'
    alias unity_cpu='salloc --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G --time=02:00:00'
    alias unity_gpu='salloc --partition=gpu --nodes=1 --ntasks=1 --gpus=1 --cpus-per-task=4 --mem=16G --time=02:00:00'

    # Run on an allocated NVIDIA GPU node. The subshell keeps these
    # container options local to this invocation.
    atlas_gpu() (
        module load apptainer/latest || return "$?"
        export ALRB_CONT_CMDOPTS="${ALRB_CONT_CMDOPTS:+$ALRB_CONT_CMDOPTS }--nv"
        if [[ -n ${CUDA_VISIBLE_DEVICES:-} ]]; then
            export APPTAINERENV_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
        fi
        source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" -c el9 "$@"
    )
fi

# Optional: uncomment and edit your actual group directory first.
# export ATLAS_WORKDIR="/work/pi_YOUR_PI/$USER/atlas"
```

Reload it in the **host shell** with `source ~/.bashrc`. The GPU workflow is then:

```bash
# Unity login node: request a GPU allocation.
unity_gpu

# After allocation, on the Ubuntu GPU compute node:
# choose your work directory, then start the EL9 container.
cd "$ATLAS_WORKDIR"
atlas_gpu
```

Set `ATLAS_WORKDIR` to your actual path first, using the optional export at the bottom of the snippet or the work-directory instructions above. If your allocated shell has not loaded the new function yet, run `source ~/.bashrc` there.

`unity_gpu` requests resources; `atlas_gpu` loads Apptainer and starts EL9 with `--nv` on the allocated node. The function preserves existing `ALRB_CONT_CMDOPTS` options, passes the current allocation's `CUDA_VISIBLE_DEVICES`, and confines the exports to its subshell. Adding the definition to `.bashrc` does not start a container at login. You can pass extra ATLAS container arguments, for example `atlas_gpu -m /another/path` if a required path is not already visible.

For CPU work, continue to use `unity_cpu`, then the host preparation and `setupATLAS -c el9` commands above.

You may also add your edited `ATLAS_WORKDIR` export. Keep module loading and software startup inside explicitly invoked commands or functions, rather than executing them automatically when `.bashrc` is read. This avoids unexpected containers or incompatible software environments when starting new shells. In scripts, source `atlasLocalSetup.sh` explicitly; non-interactive Bash does not normally expand aliases.

## 8. End or reconnect to a session {#sessions}

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

Documentation reviewed: **7 November 2026**. Rafael reported a successful test of the interactive recipe, including **`/work` visibility without an explicit mount**, and confirmed **`nvidia-smi` works inside EL9 with explicit `--nv` through `ALRB_CONT_CMDOPTS`**. The exact node, release, and GPU framework were not recorded; check those for your own analysis.
