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

