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
