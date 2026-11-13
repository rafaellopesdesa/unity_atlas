# Source this file from ~/.bashrc; it defines a command but creates no credential.
# Run inside EL9 after lsetup rucio, or supply an isolated launcher as argument 2.
atlas_proxy() {
    local duration=${1:-12:00} launcher=${2:-}
    local cert="$HOME/.globus/usercert.pem" key="$HOME/.globus/userkey.pem"
    local directory=${ATLAS_PROXY_DIR:-} temporary proxy_left ac_left seconds
    local created=0 valid=1
    local -a runner=()
    if (( $# > 2 )) || [[ ! $duration =~ ^([0-9]{1,4}):([0-5][0-9])$ ]]; then
        echo 'Usage: atlas_proxy [HH:MM] [/absolute/path/to/launcher]' >&2
        return 2
    fi
    if (( 10#${BASH_REMATCH[1]} == 0 && 10#${BASH_REMATCH[2]} == 0 )); then
        echo 'Request a positive proxy lifetime.' >&2
        return 2
    fi
    if [[ -n $launcher ]]; then
        if [[ $launcher != /* || ! -f $launcher || ! -x $launcher ]]; then
            echo 'The launcher must be an executable file with an absolute path.' >&2
            return 2
        fi
        runner=("$launcher")
    elif ! command -v voms-proxy-init >/dev/null || ! command -v voms-proxy-info >/dev/null; then
        echo 'Inside a fresh EL9 session, run lsetup rucio first, or supply the MCP launcher.' >&2
        return 1
    fi
    if [[ ! -f $cert || ! -r $cert || ! -f $key || ! -r $key ]]; then
        echo 'Cannot read ~/.globus/usercert.pem and userkey.pem inside this container.' >&2
        return 1
    fi

    if [[ -n $directory && ( -e $directory || -L $directory ) ]]; then
        if [[ ! $directory =~ ^/tmp/atlas-proxy\.[[:alnum:]]{8}$ ||
              ! -d $directory || -L $directory || ! -O $directory ||
              $(stat -c %a -- "$directory") != 700 ]]; then
            echo 'ATLAS_PROXY_DIR is not a private owned session directory; unset it and retry.' >&2
            return 1
        fi
        # Do not replace a different credential selected explicitly by the user.
        if [[ -n ${X509_USER_PROXY:-} && $X509_USER_PROXY != "$directory/x509up" ]]; then
            directory=
        fi
    else
        directory=
    fi
    if [[ -z $directory ]]; then
        directory=$(mktemp -d /tmp/atlas-proxy.XXXXXXXX) || return 1
        created=1
    fi
    if ! temporary=$(mktemp "$directory/.x509up.XXXXXXXX"); then
        if (( created )); then rmdir -- "$directory"; fi
        return 1
    fi

    # Keep the caller's umask and its current proxy unchanged if creation fails.
    if (umask 077; "${runner[@]}" voms-proxy-init \
            -voms atlas -valid "$duration" -cert "$cert" -key "$key" -out "$temporary") \
        && "${runner[@]}" voms-proxy-info -file "$temporary" -exists \
        && "${runner[@]}" voms-proxy-info -file "$temporary" -acexists atlas \
        && proxy_left=$("${runner[@]}" voms-proxy-info -file "$temporary" -timeleft) \
        && ac_left=$("${runner[@]}" voms-proxy-info -file "$temporary" -actimeleft); then
        if [[ ! $proxy_left =~ ^[0-9]+$ || -z $ac_left ]] || (( 10#$proxy_left <= 0 )); then
            valid=0
        fi
        while IFS= read -r seconds; do
            if [[ ! $seconds =~ ^[0-9]+$ ]] || (( 10#$seconds <= 0 )); then valid=0; fi
        done <<< "$ac_left"
    else
        valid=0
    fi
    if (( valid )) && chmod 600 "$temporary" && mv -fT -- "$temporary" "$directory/x509up"; then
        export ATLAS_PROXY_DIR="$directory"
        export X509_USER_PROXY="$directory/x509up"
        printf 'Proxy: %s\nRemaining proxy lifetime: %s seconds\nVOMS lifetime(s): %s seconds\n' \
            "$X509_USER_PROXY" "$proxy_left" "$ac_left"
        return 0
    fi
    rm -f -- "$temporary"
    if (( created )); then rmdir -- "$directory"; fi
    echo 'Proxy creation or validation failed; the previous proxy and exports were preserved.' >&2
    return 1
}
