#!/bin/bash
# Run grid/MCP tools in the adjacent Pixi environment, without changing
# the ATLAS environment inherited by Codex itself. Never write setup chatter
# to stdout: stdio MCP reserves that stream for its protocol.
# ATLAS_MCP_PIXI may override the default $HOME/.pixi/bin/pixi executable.
if [[ $# -eq 0 ]]; then
    echo "Usage: atlas-mcp-env.sh COMMAND [ARGUMENT ...]" >&2
    exit 2
fi

atlas_mcp_pixi=${ATLAS_MCP_PIXI:-"$HOME/.pixi/bin/pixi"}
if [[ ! -x $atlas_mcp_pixi ]]; then
    echo "Pixi is not executable at: $atlas_mcp_pixi" >&2
    echo "Install Pixi there or set ATLAS_MCP_PIXI to its absolute executable path." >&2
    exit 1
fi
atlas_mcp_dir=$(dirname "$(readlink -f "$0")")
atlas_mcp_manifest="$atlas_mcp_dir/pixi.toml"
if [[ ! -r $atlas_mcp_manifest || ! -r $atlas_mcp_dir/pixi.lock ]]; then
    echo "Missing adjacent pixi.toml or pixi.lock; install this MCP environment first." >&2
    echo "Follow the Codex Agents chapter's clean-environment pixi install command." >&2
    exit 1
fi

# Permit help/import checks and proxy creation before a proxy exists. The
# actual server processes must start with an explicit, readable user proxy.
atlas_mcp_command=${1##*/}
if [[ ( $atlas_mcp_command == rucio-mcp || $atlas_mcp_command == ami-mcp ) \
      && ${2:-} == serve ]]; then
    if [[ -z ${X509_USER_PROXY:-} || ! -f $X509_USER_PROXY || ! -r $X509_USER_PROXY ]]; then
        echo "Set X509_USER_PROXY and create a readable VOMS proxy before starting MCP." >&2
        echo "Run voms-proxy-init interactively through this wrapper, then retry." >&2
        exit 1
    fi
    if [[ $atlas_mcp_command == rucio-mcp && -z ${RUCIO_ACCOUNT:-} ]]; then
        echo "Set RUCIO_ACCOUNT to your ATLAS Rucio account before starting Rucio MCP." >&2
        exit 1
    fi
fi

atlas_mcp_user=$(id -un) || exit "$?"
atlas_mcp_env=(
    "HOME=$HOME"
    "USER=$atlas_mcp_user"
    "LOGNAME=$atlas_mcp_user"
    "PATH=/usr/bin:/bin"
    "LANG=C.UTF-8"
    "ATLAS_PMGXSEC_PATH=${ATLAS_PMGXSEC_PATH:-/cvmfs/atlas.cern.ch/repo/sw/database/GroupData/dev/PMGTools}"
)
if [[ ${X509_USER_PROXY+x} ]]; then
    atlas_mcp_env+=("X509_USER_PROXY=$X509_USER_PROXY")
fi
if [[ ${RUCIO_ACCOUNT+x} ]]; then
    atlas_mcp_env+=("RUCIO_ACCOUNT=$RUCIO_ACCOUNT")
fi

# Pixi activation supplies its own Python, libraries, and grid CA bundle.
# Do not add --clean-env here: it would discard the proxy/account variables
# explicitly supplied above. env -i already removes the parent's ATLAS setup.
exec /usr/bin/env -i "${atlas_mcp_env[@]}" "$atlas_mcp_pixi" --quiet run \
    --locked --manifest-path "$atlas_mcp_manifest" "$@"
