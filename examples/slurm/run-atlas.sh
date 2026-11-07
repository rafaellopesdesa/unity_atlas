#!/bin/bash
# This script runs inside the EL9 container.
unity_atlas_release=${1:?Missing ATLAS project and version}
unity_atlas_run_dir=${2:?Missing output directory}
unity_atlas_cpus=${3:-1}
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
