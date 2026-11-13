#!/bin/bash -l
#SBATCH --job-name=atlas-dataset
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err
#SBATCH --export=NONE

# Submit from the frozen campaign directory; supply --array on the command line.
if [[ $# -lt 2 || $# -gt 3 || -z $1 || -z $2 ]]; then
    echo 'Usage: sbatch --array=... atlas-dataset.sbatch "$USER_PI" "$PROXY_REL" [offset]' >&2
    exit 2
fi
unity_dataset_pi=$1
unity_dataset_proxy_rel=$2
unity_dataset_offset=${3:-0}
if [[ ! $unity_dataset_offset =~ ^[0-9]{1,9}$ ||
      ! ${SLURM_ARRAY_TASK_ID:-} =~ ^[0-9]{1,9}$ ]]; then
    echo 'Use a nonnegative offset and submit this script as a Slurm array.' >&2
    exit 2
fi
unity_dataset_index=$((10#$unity_dataset_offset + 10#$SLURM_ARRAY_TASK_ID))
unity_dataset_user=${SLURM_JOB_USER:?Missing Slurm username}
cd "${SLURM_SUBMIT_DIR:?Submit from the campaign directory}" || exit 1
unity_dataset_campaign=$(pwd -P) || exit 1
sha256sum --check --strict campaign.sha256 || exit 1
unity_dataset_payload="$unity_dataset_campaign/run-dataset.sh"
if [[ ! -r $unity_dataset_payload ]]; then
    echo "Cannot read payload: $unity_dataset_payload" >&2
    exit 1
fi

# The credential must cover the remaining allocation plus a 15-minute margin.
if [[ ! ${SLURM_JOB_END_TIME:-} =~ ^[0-9]+$ ]]; then
    echo 'Slurm did not provide SLURM_JOB_END_TIME; cannot check proxy lifetime.' >&2
    exit 1
fi
unity_dataset_now=$(date +%s) || exit 1
unity_dataset_remaining=$((SLURM_JOB_END_TIME - unity_dataset_now))
if (( unity_dataset_remaining <= 0 )); then
    echo 'The Slurm allocation has no remaining wall time.' >&2
    exit 1
fi
unity_dataset_required=$((unity_dataset_remaining + 900))

module load apptainer/latest || exit "$?"
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
if [[ ! -r $ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh ]]; then
    echo "ATLASLocalRootBase is unavailable on $(hostname)." >&2
    exit 1
fi

# Explicit arguments survive Slurm/Apptainer environment filtering.
printf -v unity_dataset_command '%q ' bash "$unity_dataset_payload" \
    "$unity_dataset_campaign" "$unity_dataset_index" \
    "${SLURM_CPUS_PER_TASK:-1}" "$unity_dataset_pi" "$unity_dataset_user" \
    "$unity_dataset_required" "$unity_dataset_proxy_rel"
printf 'Array %s task %s, manifest index %s, host %s\n' \
    "$SLURM_ARRAY_JOB_ID" "$SLURM_ARRAY_TASK_ID" "$unity_dataset_index" "$(hostname)"
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" \
    -c el9 -r "$unity_dataset_command"
unity_dataset_status=$?
printf 'Container command exited with status %s\n' "$unity_dataset_status"
exit "$unity_dataset_status"
