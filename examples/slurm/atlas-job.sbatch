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
