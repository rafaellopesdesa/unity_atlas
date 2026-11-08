#!/bin/bash -l
# CPU-first RemoteCommand launcher. See the VS Code chapter before use.
# Usage: atlas-vscode-ssh.sh /absolute/path/to/allocation-config.sh
if [[ $# -ne 1 || $1 != /* || ! -r $1 ]]; then
    echo "Usage: atlas-vscode-ssh.sh /absolute/path/to/allocation-config.sh" >&2
    exit 2
fi
unity_vscode_config=$1
set --
source "$unity_vscode_config" </dev/null >&2 || exit "$?"
unset BASH_ENV
for unity_vscode_key in ATLAS_VSCODE_JOB_ID ATLAS_VSCODE_NODE \
    ATLAS_VSCODE_IMAGE ATLAS_VSCODE_RELEASE ATLAS_VSCODE_WORKDIR; do
    if [[ -z ${!unity_vscode_key} ]]; then
        echo "Missing setting: $unity_vscode_key" >&2
        exit 2
    fi
done
if [[ ! $ATLAS_VSCODE_JOB_ID =~ ^[0-9]+$ || \
      $(hostname -s) != "$ATLAS_VSCODE_NODE" ]]; then
    echo "Wrong compute node or invalid job ID; refresh the allocation config." >&2
    exit 1
fi
# Require one unambiguous running allocation on this node. Unity's SSH
# service is responsible for job adoption; this check does not replace it.
unity_vscode_jobs=$(squeue --noheader --user="$(id -un)" \
    --nodelist="$ATLAS_VSCODE_NODE" --states=RUNNING --format='%A') || exit "$?"
# squeue may pad its fields. Accept surrounding whitespace, but not a
# second job ID (including a duplicate row).
if [[ ! $unity_vscode_jobs =~ ^[[:space:]]*$ATLAS_VSCODE_JOB_ID[[:space:]]*$ ]]; then
    echo "Expected exactly this running job on the node: $ATLAS_VSCODE_JOB_ID" >&2
    exit 1
fi
if [[ ! -r $ATLAS_VSCODE_IMAGE || ! -d $ATLAS_VSCODE_WORKDIR ]]; then
    echo "Check the resolved EL9 image and shared work directory." >&2
    exit 1
fi
unity_vscode_dir=$(dirname "$(readlink -f "$0")")
unity_vscode_inner="$unity_vscode_dir/atlas-vscode-shell.sh"
if [[ ! -r $unity_vscode_inner ]]; then
    echo "Missing companion script: $unity_vscode_inner" >&2
    exit 1
fi
module load apptainer/latest </dev/null >&2 || exit "$?"
cd "$ATLAS_VSCODE_WORKDIR" || exit 1
# A module may have introduced another noninteractive startup hook.
unset BASH_ENV

# Direct exec keeps VS Code's input stream intact. Unlike the interactive
# ALRB launcher, this helper states its essential mounts explicitly.
exec apptainer exec --cleanenv \
    --bind /cvmfs:/cvmfs --bind /work:/work --bind "$HOME:$HOME" \
    "$ATLAS_VSCODE_IMAGE" \
    /bin/bash --noprofile --norc "$unity_vscode_inner" \
    "$ATLAS_VSCODE_RELEASE" "$ATLAS_VSCODE_WORKDIR" \
    "${ATLAS_VSCODE_BUILD_SETUP:-}" "${ATLAS_VSCODE_CPUS:-1}"
