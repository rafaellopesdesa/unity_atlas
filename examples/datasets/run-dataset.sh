#!/bin/bash
# Runs inside EL9. Long-lived keys and passphrases are never used by this script.
if [[ $# -ne 7 ]]; then
    echo 'Expected: campaign index cpus USER_PI USER required_seconds proxy_relative_path' >&2
    exit 2
fi
unity_dataset_campaign=$1
unity_dataset_index=$2
unity_dataset_cpus=$3
export USER_PI=$4
export USER=$5
unity_dataset_required=$6
unity_dataset_proxy_rel=$7
if [[ ! $unity_dataset_index =~ ^[0-9]+$ ||
      ! $unity_dataset_cpus =~ ^[1-9][0-9]*$ ||
      ! $unity_dataset_required =~ ^[1-9][0-9]*$ ]]; then
    echo 'Invalid manifest index, CPU count, or required proxy lifetime.' >&2
    exit 2
fi
case "$unity_dataset_proxy_rel" in
    .globus/unity-atlas-proxies/*/x509up) ;;
    *) echo 'Proxy must be a relative .globus/unity-atlas-proxies/CAMPAIGN/x509up path.' >&2; exit 2 ;;
esac
case "/$unity_dataset_proxy_rel/" in
    */../*|*/./*|*//*) echo 'Proxy path must not contain .., ., or empty components.' >&2; exit 2 ;;
esac
cd "$unity_dataset_campaign" || exit 1
sha256sum --check --strict campaign.sha256 || exit 1
set --
shopt -s expand_aliases
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
unity_dataset_status=$?
if (( unity_dataset_status != 0 )); then exit "$unity_dataset_status"; fi

# HOME is resolved inside EL9, where the shared home may have a different path.
unity_dataset_shared_proxy="$HOME/$unity_dataset_proxy_rel"
if [[ ! -f $unity_dataset_shared_proxy || -L $unity_dataset_shared_proxy ||
      ! -O $unity_dataset_shared_proxy || ! -r $unity_dataset_shared_proxy ]]; then
    echo 'Shared proxy is missing, unreadable, a symlink, or owned by another user.' >&2
    exit 1
fi
unity_dataset_mode=$(stat -c %a -- "$unity_dataset_shared_proxy") || exit 1
if [[ $unity_dataset_mode != 600 && $unity_dataset_mode != 400 ]]; then
    echo 'Shared proxy must have mode 600 or 400; correct it before retrying.' >&2
    exit 1
fi
umask 077
unity_dataset_proxy_dir=$(mktemp -d /tmp/atlas-job-proxy.XXXXXXXX) || exit 1
trap 'rm -f -- "$unity_dataset_proxy_dir/x509up" "$unity_dataset_proxy_dir/ca-dir"; rmdir -- "$unity_dataset_proxy_dir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cp -- "$unity_dataset_shared_proxy" "$unity_dataset_proxy_dir/x509up" || exit 1
chmod 600 "$unity_dataset_proxy_dir/x509up" || exit 1
export X509_USER_PROXY="$unity_dataset_proxy_dir/x509up"

# Keep the grid client's Python/library setup out of the analysis environment.
(
    lsetup rucio || exit "$?"
    unity_dataset_ca_dir=${X509_CERT_DIR:-/etc/grid-security/certificates}
    if [[ $unity_dataset_ca_dir != /* || $unity_dataset_ca_dir == *$'\n'* ||
          ! -d $unity_dataset_ca_dir || ! -r $unity_dataset_ca_dir || ! -x $unity_dataset_ca_dir ]]; then
        echo 'No readable grid CA directory: check X509_CERT_DIR from lsetup rucio.' >&2
        exit 1
    fi
    export X509_CERT_DIR="$unity_dataset_ca_dir"
    printf '%s\n' "$unity_dataset_ca_dir" > "$unity_dataset_proxy_dir/ca-dir" || exit 1
    voms-proxy-info -file "$X509_USER_PROXY" -exists || exit 1
    voms-proxy-info -file "$X509_USER_PROXY" -acexists atlas || exit 1
    unity_dataset_proxy_left=$(voms-proxy-info -file "$X509_USER_PROXY" -timeleft) || exit 1
    unity_dataset_ac_left=$(voms-proxy-info -file "$X509_USER_PROXY" -actimeleft) || exit 1
    if [[ ! $unity_dataset_proxy_left =~ ^[0-9]+$ || -z $unity_dataset_ac_left ]]; then
        echo 'Could not determine proxy and VOMS attribute lifetimes.' >&2
        exit 1
    fi
    if (( unity_dataset_proxy_left < unity_dataset_required )); then
        echo 'Proxy expires too soon: renew the shared proxy and retry this task.' >&2
        exit 1
    fi
    while IFS= read -r unity_dataset_seconds; do
        if [[ ! $unity_dataset_seconds =~ ^[0-9]+$ ]] ||
           (( unity_dataset_seconds < unity_dataset_required )); then
            echo 'VOMS attributes expire too soon: renew the shared proxy and retry this task.' >&2
            exit 1
        fi
    done <<< "$unity_dataset_ac_left"
    printf 'Proxy and VOMS attributes cover the required %s seconds.\n' "$unity_dataset_required"
)
unity_dataset_status=$?
if (( unity_dataset_status != 0 )); then exit "$unity_dataset_status"; fi
IFS= read -r unity_dataset_ca_dir < "$unity_dataset_proxy_dir/ca-dir" || exit 1

unity_dataset_release=$(python3 - "$unity_dataset_campaign/analysis-config.json" <<'PY'
import json
import sys

with open(sys.argv[1]) as stream:
    release = json.load(stream).get("release")
parts = release.split(",") if isinstance(release, str) else []
if (len(parts) != 2 or any(not part or part != part.strip() for part in parts)
        or parts[1].lower() == "latest"):
    raise SystemExit("analysis-config.json needs an exact release such as project,version")
print(release)
PY
)
unity_dataset_status=$?
if (( unity_dataset_status != 0 )); then exit "$unity_dataset_status"; fi
asetup "$unity_dataset_release"
unity_dataset_status=$?
if (( unity_dataset_status != 0 )); then exit "$unity_dataset_status"; fi

set -euo pipefail
# Restore only the grid trust path after asetup, not the Rucio Python environment.
export X509_CERT_DIR="$unity_dataset_ca_dir"
export OMP_NUM_THREADS="$unity_dataset_cpus"
python -u "$unity_dataset_campaign/analyse-file.py" \
    --campaign "$unity_dataset_campaign" --index "$unity_dataset_index" \
    --cpus "$unity_dataset_cpus"
