A batch job needs the same environment as an interactive session. Slurm starts the job on an allocated **Ubuntu compute node**; the job loads Apptainer, enters **EL9**, selects an ATLAS release, and runs the analysis there.

You submit with `sbatch` from a Unity login node. There is no preceding `salloc`, and you can disconnect after submission. The batch allocation and its wall-time limit are managed by Slurm.

::: {.callout}
**Prerequisite:** first complete [Setting up the environment](../setting-up-environment/), including the one-time directories and [`.bashrc` settings](../setting-up-environment/#bashrc), and choose an exact ATLAS release that works for your analysis. This chapter uses your saved `USER_PI`, Unity `$USER`, and `ATLAS_WORKDIR`.
:::

## 1. Separate scheduling from the analysis {#workflow}

The example uses two files:

| File | Where it runs | What it does |
| --- | --- | --- |
| `atlas-job.sbatch` | Ubuntu worker node | Requests resources through `#SBATCH` directives, loads the container runtime, and starts the EL9 command. |
| `run-atlas.sh` | Inside the EL9 container | Initializes ATLAS, selects the requested release, and runs a small PyROOT test. |

The key ATLAS option is **`-r`**, which runs a command inside the container without opening an interactive prompt. The wrapper invokes the setup script directly:

```bash
# Pattern used in the batch script; the variables are defined there.
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" \
    -c el9 -r "$unity_atlas_command"
```

This is the scripted equivalent of `setupATLAS -c el9`, followed by commands inside the container. Simply writing `setupATLAS -c el9` on one line and your analysis on the next does not put that next line inside the container. Keep the analysis in the command passed to `-r`.

The [US ATLAS benchmarking examples](https://github.com/usatlas/af-benchmarking/blob/main/README.md) use this non-interactive interface. Our wrapper adapts it to Unity's module and Slurm configuration.

## 2. Prepare a shared job directory {#prepare}

Start from a **fresh Ubuntu login shell**, outside an interactive ATLAS container. Your `.bashrc` already defines `ATLAS_WORKDIR="/work/${USER_PI}/${USER}/atlas"`; create a job subdirectory there:

```bash
# Unity login node
mkdir -p "$ATLAS_WORKDIR/jobs/atlas-test"
cd "$ATLAS_WORKDIR/jobs/atlas-test"
mkdir -p logs

curl --fail --location --output atlas-job.sbatch \
    https://raw.githubusercontent.com/rafaellopesdesa/unity_atlas/main/examples/slurm/atlas-job.sbatch
curl --fail --location --output run-atlas.sh \
    https://raw.githubusercontent.com/rafaellopesdesa/unity_atlas/main/examples/slurm/run-atlas.sh
```

You can also save the files directly: [atlas-job.sbatch](../examples/slurm/atlas-job.sbatch) and [run-atlas.sh](../examples/slurm/run-atlas.sh). Both belong in the directory from which you will submit. No executable permission is required here: Slurm reads the submission script, and the container runs the payload with `bash`.

**Create `logs/` before submitting.** Slurm opens the output files before the script runs, so creating that directory inside the job would be too late.

Slurm transfers the submission script, but it does **not** transfer your payload, analysis code, input files, or software build. They must remain accessible on shared storage. Avoid editing `run-atlas.sh` or its dependencies while jobs using them are queued or running; keep a separate copy for a new version.

## 3. The worker-node script {#batch-script}

`atlas-job.sbatch` requests one CPU, 4 GB of memory, and 15 minutes for the small test. Its login Bash shell initializes the host's module environment. It creates a separate `runs/JOB_ID/` directory for every submission.

```bash
#!/bin/bash -l
#SBATCH --job-name=atlas-test
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
#SBATCH --export=NONE

# This script runs on the allocated Ubuntu worker node.
if [[ $# -ne 2 || $1 != *,* || -z $2 ]]; then
    echo 'Usage: sbatch atlas-job.sbatch AnalysisBase,VERSION "$USER_PI"' >&2
    exit 2
fi
unity_atlas_release=$1
unity_atlas_pi=$2
unity_atlas_user=${SLURM_JOB_USER:?Missing Slurm username}
cd "${SLURM_SUBMIT_DIR:?Submit from your shared job directory}" || exit 1
unity_atlas_payload="$PWD/run-atlas.sh"
if [[ ! -r "$unity_atlas_payload" ]]; then
    echo "Cannot read payload: $unity_atlas_payload" >&2
    exit 1
fi
unity_atlas_run_dir="$PWD/runs/${SLURM_JOB_ID:?Missing Slurm job ID}"
mkdir -p "$unity_atlas_run_dir" || exit 1

# Load the container runtime on the host, before entering EL9.
module load apptainer/latest || exit "$?"
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
if [[ ! -r "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" ]]; then
    echo "ATLASLocalRootBase is unavailable on $(hostname)" >&2
    exit 1
fi

# Enable NVIDIA passthrough only when this job has allocated GPUs.
if [[ -n ${SLURM_JOB_GPUS:-} ]]; then
    export ALRB_CONT_CMDOPTS="${ALRB_CONT_CMDOPTS:+$ALRB_CONT_CMDOPTS }--nv"
    if [[ ${CUDA_VISIBLE_DEVICES+x} ]]; then
        export APPTAINERENV_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
    fi
fi

# Pass arguments explicitly; do not depend on host variables surviving
# the container's environment filtering. %q quotes each Bash argument.
printf -v unity_atlas_command 'bash %q %q %q %q %q %q' \
    "$unity_atlas_payload" "$unity_atlas_release" "$unity_atlas_run_dir" \
    "${SLURM_CPUS_PER_TASK:-1}" "$unity_atlas_pi" "$unity_atlas_user"
printf 'Job %s on %s; release %s; output %s\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$unity_atlas_release" "$unity_atlas_run_dir"
cd "$unity_atlas_run_dir" || exit 1

# -r runs the payload inside the container and then leaves the container.
# Unity exposes /work inside the container; no -m is needed for it.
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" \
    -c el9 -r "$unity_atlas_command"
unity_atlas_status=$?
printf 'Container command exited with status %s\n' "$unity_atlas_status"
exit "$unity_atlas_status"
```

The wrapper sources ATLASLocalRootBase explicitly instead of depending on the interactive `setupATLAS` alias in `.bashrc`. The `--export=NONE` directive avoids importing the submission shell's full environment; Slurm still supplies its job variables and may initialize the user's login environment. This is not a completely empty environment. The submission commands pass your saved `USER_PI` as an argument; the wrapper obtains your username from `SLURM_JOB_USER` and passes both into the payload. This keeps `/work/${USER_PI}/${USER}` and `/project/${USER_PI}/${USER}` usable in scripts without relying on `.bashrc` being read there. Keep software and container startup out of your shell startup files, as described in the [shell-configuration section](../setting-up-environment/#bashrc).

Unity exposes `/work` inside the container, so the standard command needs no `-m /work`. For another filesystem that is missing inside EL9, use the [mount guidance in the environment chapter](../setting-up-environment/#container) and add the corresponding `-m /actual/path` to the container launch.

This is a **single-node, single-process** job. Slurm already runs the batch script on the worker, so it does not need an additional `srun` for this example. MPI and multiple simultaneous tasks require a different launch pattern. If you later introduce `srun`, note that this script uses `--export=NONE`: use `srun --export=ALL ...` when the step needs the environment you have prepared.

## 4. The script inside EL9 {#payload}

`run-atlas.sh` starts a fresh Bash process inside the container. It initializes the ATLAS command definitions, runs `asetup` for the release passed at submission, and creates `hist.root` without requiring any input data or credentials.

```bash
#!/bin/bash
# This script runs inside the EL9 container.
unity_atlas_release=${1:?Missing ATLAS project and version}
unity_atlas_run_dir=${2:?Missing output directory}
unity_atlas_cpus=${3:-1}
# These were passed explicitly, not inherited from an interactive .bashrc.
export USER_PI=${4:?Missing Unity PI directory}
export USER=${5:?Missing Unity username}
cd "$unity_atlas_run_dir" || exit 1
# Do not let a sourced setup script interpret the payload's arguments.
set --

# A new Bash process needs its own ATLAS command definitions.
# ALRB defines aliases such as asetup; Bash scripts must enable them.
shopt -s expand_aliases
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
unity_atlas_status=$?
if (( unity_atlas_status != 0 )); then
    exit "$unity_atlas_status"
fi
asetup "$unity_atlas_release"
unity_atlas_status=$?
if (( unity_atlas_status != 0 )); then
    exit "$unity_atlas_status"
fi

# Enable strict error handling after the external setup scripts finish.
set -euo pipefail
export OMP_NUM_THREADS="$unity_atlas_cpus"
printf 'Container OS:\n'
cat /etc/os-release
printf '\nWorking directory: %s\n' "$PWD"

# Replace this smoke test with your analysis command.
python -u - <<'PY'
import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gRandom.SetSeed(12345)
output = ROOT.TFile.Open("hist.root", "RECREATE")
if not output or output.IsZombie():
    raise RuntimeError("Cannot create hist.root")
hist = ROOT.TH1D("example", "ATLAS on Unity; x; Entries", 50, -5, 5)
hist.FillRandom("gaus", 10000)
hist.Write()
output.Close()
print("ROOT version:", ROOT.gROOT.GetVersion())
print("Wrote hist.root with 10000 entries")
PY
test -s hist.root
printf 'Payload finished successfully.\n'
```

`shopt -s expand_aliases` lets this non-interactive Bash script use the aliases defined by ATLASLocalRootBase, including `asetup`. The setup and `asetup` commands are on separate lines so those definitions are available before the release command is parsed.

External setup scripts run before strict Bash error handling is enabled; their return codes are checked explicitly. Once setup finishes, `set -euo pipefail` makes a failed analysis command stop the payload. The wrapper returns the container command's status to Slurm. When adapting the example, keep this error handling: a final successful `echo` must not hide a failed analysis.

## 5. Submit and inspect the result {#submit}

Use the **same project and exact release version** selected in the [environment chapter](../setting-up-environment/#software), after confirming it works for your analysis. `ATLAS_RELEASE` has the same `project,version` format here. Do not enter a literal placeholder or a moving `latest` version. The prompt below sets it in your login shell; the batch job itself never prompts for input.

```bash
# Still in the directory containing both scripts and logs/.
read -r -p 'ATLAS project,version: ' ATLAS_RELEASE
if [[ "$ATLAS_RELEASE" == *,* ]]; then
    if JOB_ID=$(sbatch --parsable atlas-job.sbatch "$ATLAS_RELEASE" "$USER_PI"); then
        JOB_ID=${JOB_ID%%;*}
        printf 'Submitted job: %s\n' "$JOB_ID"
    fi
else
    echo 'Enter a project and exact version, separated by a comma.'
fi
```

Record the returned job ID. In a later login session, set `JOB_ID` to that number before using these commands:

```bash
# Queued/running jobs; a completed job will disappear from squeue.
squeue --jobs="$JOB_ID"

# Accounting, including the batch step; may take a short time to update.
sacct --jobs="$JOB_ID" \
      --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS

# These files appear once the job starts.
tail -n 50 "logs/atlas-test-${JOB_ID}.out"
tail -n 50 "logs/atlas-test-${JOB_ID}.err"
ls -lh "runs/${JOB_ID}/hist.root"
```

For a successful smoke test, check **all three**:

- Slurm reports `COMPLETED` with `ExitCode` equal to `0:0`.
- The output log identifies EL9, reports the ROOT version, and ends with the successful payload message and container status zero.
- `runs/JOB_ID/hist.root` exists and is nonempty. In an interactive session with the same release, you can open it and inspect the histogram `example`, which should have 10,000 entries.

`MaxRSS` is generally reported for a step such as `JOB_ID.batch`; keep those rows in the accounting output. Check both logs when a job fails. For Slurm, the first number in `ExitCode` is the return code and the second is the terminating signal.

To cancel a queued or running job **when you want to stop it**:

```bash
scancel "$JOB_ID"
```

## 6. Replace the test with your analysis {#analysis}

Replace the Python block and the `test -s hist.root` check in `run-atlas.sh` with your analysis command and an appropriate output check. Keep the release setup and run-directory change. Relative output paths then land in `runs/JOB_ID/`; use absolute paths for shared inputs and code.

For example, use the analysis checkout under your work area and choose an input file from your `/project` allocation. Replace `PROJECT_NAME` with your repository's directory name and use its actual script/input paths. `USER_PI` and `USER` are set by the supplied payload from the arguments passed by the worker script:

```bash
# Inside run-atlas.sh, after asetup and set -euo pipefail.
python -u "/work/${USER_PI}/${USER}/atlas/PROJECT_NAME/run.py" \
    --input "/project/${USER_PI}/${USER}/input.root" \
    --output result.root
test -s result.root
```

If your analysis uses a compiled ATLAS package, build it in an EL9 allocation with the same release and platform, then source that build's exact `setup.sh` after `asetup` in the payload. Keep the build accessible on shared storage. Do not build the same directory concurrently from multiple jobs.

Remote data access and authentication need their own setup; having software on CVMFS does not grant access to protected data. The initial smoke test deliberately needs neither.

### Adjust CPU, memory, and time

Command-line `sbatch` options override the corresponding `#SBATCH` directives. For example, once your analysis is configured to use four CPUs:

```bash
sbatch --cpus-per-task=4 --mem=16G --time=02:00:00 \
    atlas-job.sbatch "$ATLAS_RELEASE" "$USER_PI"
```

Requesting four CPUs does not automatically parallelize Python or ROOT. The example passes the CPU allocation into the container and sets `OMP_NUM_THREADS`; configure your application's own thread or worker count as needed. Keep that count within the allocation. `--mem` here is memory per node, not per CPU.

Keep directives at the top of the file, before shell commands. Slurm reads them before executing Bash, so `#SBATCH --output=$HOME/...` does not expand `$HOME`. Use a literal path, a Slurm filename token such as `%j` (job ID), or an option on the `sbatch` command line.

### Request an NVIDIA GPU

The same wrapper detects an allocated GPU through `SLURM_JOB_GPUS`, appends `--nv` to `ALRB_CONT_CMDOPTS`, and forwards Slurm's `CUDA_VISIBLE_DEVICES` selection when present. This uses the same passthrough option as the [interactive GPU recipe](../setting-up-environment/#gpu). The batch script sets it itself; `atlas_gpu` remains the shortcut for interactive shells. Request the GPU at submission:

```bash
sbatch --partition=gpu --gpus=1 --cpus-per-task=4 \
    --mem=16G --time=02:00:00 atlas-job.sbatch "$ATLAS_RELEASE" "$USER_PI"
```

Add `nvidia-smi` after setup inside `run-atlas.sh` to inspect device visibility, then use a CUDA-capable application and compatible software environment. The provided histogram test runs on the CPU even when a GPU is allocated; it does not validate a GPU framework. Do not replace Slurm's device selection with a hard-coded GPU number.

## Troubleshooting {#troubleshooting}

| Symptom | What to check |
| --- | --- |
| No log files yet | A pending job has not started. Check `squeue`; also confirm `logs/` existed before submission and is writable. |
| `module: command not found` | Keep the login-shell shebang `#!/bin/bash -l`; check host shell initialization and Unity's module instructions. |
| `setupATLAS` or `asetup` is not found | Use the supplied explicit setup and alias-expansion sequence; an interactive `.bashrc` alias is not enough for batch scripts. |
| Script or input missing inside the container | Submit from the shared job directory, keep the payload there, and verify its absolute path inside EL9. Add `-m` only for paths not already visible. |
| Software setup fails | Confirm the exact project, release, and platform worked in a fresh interactive EL9 session. Check compute-node CVMFS access. |
| `FAILED`, `OUT_OF_MEMORY`, or `TIMEOUT` | Read both logs and the `sacct` state; fix the command or adjust the measured memory/time requirement. |
| `COMPLETED` but output is missing | Check that the payload actually ran, did not hide a failed command, and wrote to the intended run directory. Keep explicit output checks. |
| GPU unavailable inside the payload | Check the GPU resource request, `--nv` in the container launch line, Slurm's device selection, and the application's CUDA support. If `nvidia-smi` is missing, inspect startup mount warnings. |

## References {#references}

- [Unity: batch jobs with sbatch](https://docs.unity.rc.umass.edu/documentation/jobs/sbatch/) and [partitions](https://docs.unity.rc.umass.edu/documentation/cluster_specs/partitions/).
- [US ATLAS analysis-facility benchmarking examples](https://github.com/usatlas/af-benchmarking/blob/main/README.md), including ATLASLocalRootBase container commands and batch wrappers.
- [ATLAS Software Documentation](https://atlas-software.docs.cern.ch/).
- [Slurm sbatch](https://slurm.schedmd.com/sbatch.html), [sacct](https://slurm.schedmd.com/sacct.html), and [job exit codes](https://slurm.schedmd.com/job_exit_code.html).
- [Apptainer NVIDIA GPU support](https://apptainer.org/docs/user/latest/gpu.html).

**Next:** [Using Pixi](../using-pixi/) covers personal tools and project-specific package environments.

