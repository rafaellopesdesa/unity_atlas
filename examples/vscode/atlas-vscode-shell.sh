#!/bin/bash
# Runs inside EL9; leaves stdin untouched for the VS Code bootstrap script.
unity_vscode_release=${1:?Missing project and release}
unity_vscode_workdir=${2:?Missing work directory}
unity_vscode_build=${3:-}
unity_vscode_cpus=${4:-1}
set --
cd "$unity_vscode_workdir" || exit 1
shopt -s expand_aliases
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" </dev/null >&2
unity_vscode_status=$?
if (( unity_vscode_status != 0 )); then exit "$unity_vscode_status"; fi
asetup "$unity_vscode_release" </dev/null >&2
unity_vscode_status=$?
if (( unity_vscode_status != 0 )); then exit "$unity_vscode_status"; fi
if [[ -n $unity_vscode_build ]]; then
    source "$unity_vscode_build" </dev/null >&2
    unity_vscode_status=$?
    if (( unity_vscode_status != 0 )); then exit "$unity_vscode_status"; fi
fi
export OMP_NUM_THREADS="$unity_vscode_cpus"
# No strict shell options or extra stdout: VS Code supplies the next script.
unset BASH_ENV
exec /bin/bash --noprofile --norc
