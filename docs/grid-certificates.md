Use a personal grid certificate to establish your identity, register that identity with ATLAS, and create a short-lived VOMS proxy for command-line access. The proxy can then be used by Rucio, compatible storage clients, and the Rucio/AMI MCP servers described later in this guide.

Obtaining and installing the certificate is a one-time setup that you repeat when renewing or replacing it. Creating a proxy is a session task. Complete [Setting up the environment](../setting-up-environment/) first; this chapter uses its `unity_cpu`, `setupATLAS`, and `ATLAS_WORKDIR` settings.

## 1. Understand the credentials {#credentials}

| Item | Purpose and lifetime |
| --- | --- |
| Personal grid certificate | Identifies you to grid services; issued by a trusted certificate authority and renewed before its expiry. |
| Encrypted private key | Proves that the certificate belongs to you. Its passphrase is needed when creating a proxy. |
| ATLAS VO membership | Associates your identity with the ATLAS virtual organization and its approved groups. Managed through ATLAS IAM. |
| VOMS proxy | A short-lived credential containing your delegated identity and ATLAS attributes. Clients read it from the path in `X509_USER_PROXY`. |
| Unity account | Lets you log in and run jobs on Unity. It is separate from your ATLAS grid identity and Rucio account. |

A `.p12` or `.pfx` file is a PKCS#12 bundle containing the certificate and private key. This guide extracts that bundle into `usercert.pem` and an encrypted `userkey.pem`, then creates the session proxy in a private directory under `/tmp`.

## 2. Obtain a personal grid certificate {#obtain}

If you already have a valid personal grid certificate and its private key, reuse them and continue to [ATLAS registration](#register). You do not need a separate certificate for Unity.

On **your own computer**, using your browser:

1. Open the [CERN Certification Authority](https://ca.cern.ch/ca/) and sign in with your CERN account.
2. Under **Grid User certificates**, choose **New Grid User certificate** and follow the request process. This must be a personal grid-user certificate.
3. Save the certificate and private key as a password-protected PKCS#12 bundle (`.p12` or `.pfx`). Keep the original downloaded bundle if the issuance workflow supplies one.
4. Keep a protected backup and retain its password. You will need both to install the credential on Unity.

CERN checks account and registration eligibility. Its [eligibility guidance](https://ca.cern.ch/ca/Help/Default.aspx?kbid=021001) explains the requirements and alternatives if you cannot obtain a CERN certificate. A Unity account alone does not make you eligible.

If your certificate is already installed in a browser, export or back up **the certificate together with its private key** as a password-protected PKCS#12 bundle. Exporting only a public `.cer` file is insufficient. CERN provides [browser import/export help](https://ca.cern.ch/ca/Help/?fdid=6) and [macOS instructions](https://ca.cern.ch/ca/Help/?kbid=060111).

## 3. Register with ATLAS and link the certificate {#register}

Certificate issuance and ATLAS membership are separate steps. Use the browser on your own computer for registration:

1. Import the PKCS#12 bundle into your browser's personal-certificate store. In Firefox, open the certificate manager, choose **Your Certificates**, and select **Import**. Enter the bundle password when prompted.
2. Open [ATLAS IAM](https://atlas-auth.cern.ch/) with that browser. Select your grid certificate if the browser asks.
3. If you already have an ATLAS IAM account, sign in with **CERN SSO**. Otherwise choose **Apply for an account**, complete the registration and usage-policy steps, confirm the email request, and wait for approval.
4. Check that your grid certificate is linked to your account. If **Link Certificate** is offered, select it and confirm the certificate identity. The link option requires the browser to have presented a valid, trusted certificate.

Use your existing IAM account when adding a replacement certificate. Request additional groups only when needed for your work. The [ATLAS VO guide](https://atlas-software.docs.cern.ch/analysis/analysis_tutorial/basicSetup/grid_vo/) and [US ATLAS registration instructions](https://docs.sdcc.bnl.gov/experiments/usatlas/Joining_the_ATLAS_VO/) provide further details.

## 4. Install the credentials on Unity {#install}

Keep credentials in your private home directory. Do not put the bundle, private key, or proxy in your analysis repository or a shared project directory.

For a **first installation**, create the destination from your own computer. Replace `YOUR_USERNAME` with your Unity username, and adjust the local bundle filename:

```bash
# Your computer
ssh YOUR_USERNAME@login.unityhpc.org \
  'umask 077; mkdir -p "$HOME/.globus"; chmod 700 "$HOME/.globus"'
scp "$HOME/Downloads/grid-certificate.p12" \
  YOUR_USERNAME@login.unityhpc.org:.globus/usercred.p12
```

If you already have the working `usercert.pem` and `userkey.pem` pair on Unity, skip the bundle transfer and conversion. For a certificate replacement, preserve the existing pair until you have checked the replacement; the conversion commands below write those filenames.

### Enter the container {#container}

Connect to Unity and use the environment chapter's allocation and container commands:

```bash
# Your computer
ssh YOUR_USERNAME@login.unityhpc.org
```

```bash
# Unity login node
unity_cpu

# After allocation, on the Ubuntu compute node
module load apptainer/latest
cd "$ATLAS_WORKDIR"
setupATLAS -c el9
```

Check the credential directory **inside EL9**:

```bash
printf 'Container home: %s\n' "$HOME"
ls -ld "$HOME/.globus"
```

The container may expose your home at a different path than the Ubuntu host. Use the paths visible inside the container throughout this chapter. If the files are missing, check the host path and the environment chapter's [mount guidance](../setting-up-environment/#container) before continuing. A `.globus` directory under the current working directory is not necessarily `$HOME/.globus`.

### Convert a PKCS#12 bundle to PEM

For the first installation, run these commands **inside EL9**. The private key remains encrypted:

```bash
umask 077
chmod 700 "$HOME/.globus"
chmod 600 "$HOME/.globus/usercred.p12"

openssl pkcs12 -in "$HOME/.globus/usercred.p12" \
  -clcerts -nokeys -out "$HOME/.globus/usercert.pem"

openssl pkcs12 -in "$HOME/.globus/usercred.p12" \
  -nocerts -aes256 -out "$HOME/.globus/userkey.pem"

chmod 600 "$HOME/.globus/usercert.pem" "$HOME/.globus/userkey.pem"
```

OpenSSL asks for the bundle's import password. When extracting the key, it also asks you to choose and confirm a PEM passphrase. That PEM passphrase is what `voms-proxy-init` will request. Do not add `-nodes` or `-noenc`, which would remove key encryption.

Check that the files are readable and that the certificate has not expired:

```bash
ls -l "$HOME/.globus/usercert.pem" "$HOME/.globus/userkey.pem"
openssl x509 -in "$HOME/.globus/usercert.pem" \
  -noout -subject -issuer -dates
openssl pkey -in "$HOME/.globus/userkey.pem" -check -noout
```

The last command prompts for the PEM passphrase and checks the private key without printing it. These commands check the local files; the following VOMS request checks your grid credential and ATLAS membership.

## 5. Create a proxy for this session {#create-proxy}

Inside a fresh EL9 session, initialize the ATLAS grid client environment:

```bash
lsetup rucio
command -v voms-proxy-init
```

No analysis release or Pixi environment is needed for this step. The [Codex chapter](../codex-agents/#grid-auth) runs the same proxy commands through its isolated MCP launcher instead.

Choose the proxy output path **before creating it**. Use explicit paths for all three files: the certificate, private key, and output proxy. Run this once for a new session; [renew an existing proxy](#renew) at its current path when needed.

```bash
umask 077
if ATLAS_PROXY_DIR="$(mktemp -d /tmp/atlas-proxy.XXXXXXXX)"; then
    export ATLAS_PROXY_DIR
    export X509_USER_PROXY="$ATLAS_PROXY_DIR/x509up"

    voms-proxy-init \
        -voms atlas -valid 12:00 \
        -cert "$HOME/.globus/usercert.pem" \
        -key "$HOME/.globus/userkey.pem" \
        -out "$X509_USER_PROXY" \
    && voms-proxy-info -file "$X509_USER_PROXY" -timeleft
else
    echo 'Could not create a private proxy directory; stop here.' >&2
fi
```

Substitute your actual certificate/key filenames if needed. Enter the **PEM private-key passphrase** when prompted. Continue only after proxy creation succeeds and the remaining lifetime is positive. Inspect the identity, ATLAS attributes, and their expiry with:

```bash
voms-proxy-info -file "$X509_USER_PROXY" -all
```

The requested 12 hours can be shortened by certificate expiry or server policy. Inspect both the proxy and VOMS-attribute lifetimes. The exported path remains available to commands started in this terminal.

**Do not set `X509_USER_PROXY` by running `voms-proxy-info -path` before a proxy exists.** If that lookup fails, assigning its output can export an empty string. The explicit `-out` recipe above avoids that failure.

### Recommended shortcut: `atlas_proxy` {#proxy-helper}

For routine sessions, define a Bash function so that creating or renewing a proxy takes one command. This creates the **short-lived session proxy** from your installed certificate and encrypted key; obtaining or renewing the personal certificate itself still follows the earlier CA and registration steps.

Install the [atlas-proxy.sh helper](../examples/atlas-proxy.sh) **once**, on the Unity login node:

```bash
mkdir -p "$HOME/.config/unity-atlas"
curl --fail --location --output "$HOME/.config/unity-atlas/atlas-proxy.sh" \
    https://raw.githubusercontent.com/rafaellopesdesa/unity_atlas/main/examples/atlas-proxy.sh
```

Add these lines to your existing `.bashrc` if they are not already present. The environment chapter's updated [shell configuration](../setting-up-environment/#bashrc) includes them:

```bash
if [[ -r "$HOME/.config/unity-atlas/atlas-proxy.sh" ]]; then
    source "$HOME/.config/unity-atlas/atlas-proxy.sh"
fi
```

Sourcing this file only defines `atlas_proxy`; it does not contact VOMS or prompt at login. In a **fresh EL9 session**, initialize the grid tools and invoke it explicitly:

```bash
lsetup rucio
# Also load the function if this container did not read your .bashrc.
source "$HOME/.config/unity-atlas/atlas-proxy.sh"
atlas_proxy
```

It requests 12 hours by default. To request another lifetime, use `atlas_proxy 24:00`; the server or certificate may shorten the request, so inspect the lifetimes printed by the helper.

The helper uses `$HOME/.globus/usercert.pem` and `$HOME/.globus/userkey.pem` with explicit `-cert` and `-key` arguments. It creates a private session directory, supplies a nonempty `-out` path, checks the proxy and ATLAS attributes, and exports `X509_USER_PROXY` and `ATLAS_PROXY_DIR` in your current shell only after success. If your certificate/key filenames differ, adjust the two paths in your installed helper.

Calling `atlas_proxy` again in the same session renews at the same path. The replacement is validated before it replaces the old file, so failed authentication does not discard an existing proxy. Enter the private-key passphrase at the terminal; it is not stored in `.bashrc`. Run the function directly, not as `$(atlas_proxy)` or in a separate shell, because its exports must remain in the current shell.

For Codex's isolated grid tools, the optional second argument selects its launcher: `atlas_proxy 12:00 "$MCP_DIR/atlas-mcp-env.sh"`. The [Codex chapter](../codex-agents/#grid-auth) sets up that launcher. The helper does not run `lsetup` itself or change your analysis software environment.

## 6. Use the proxy with your tools {#use-proxy}

For Rucio, set the account associated with your ATLAS identity and select proxy authentication:

```bash
export RUCIO_ACCOUNT=YOUR_RUCIO_ACCOUNT
export RUCIO_AUTH_TYPE=x509_proxy
```

Your Rucio account may differ from Unity's `$USER`. These exports select an existing account; they do not create or register it. Compatible XRootD clients use the same `X509_USER_PROXY` path. The Codex MCP launcher forwards that path to its clients, which have their own authentication configuration.

Keep the proxy readable by the process that needs it. A new node or container may have a different `/tmp`, and a new terminal does not automatically inherit your exports. Recreate the proxy in the session where you will use it if the existing file is unavailable. In a Slurm job, a proxy made on another node is not automatically accessible merely because its filename is exported. [Running on datasets with Slurm](../running-on-datasets/#worker-proxy) shows how to publish a private shared copy and validate a separate proxy on each worker.

Put the helper definition in `.bashrc`, and invoke `atlas_proxy` when you need it. Do not save a temporary proxy path or invoke proxy creation automatically at login. Proxy creation establishes your identity and ATLAS attributes; an individual service still applies its account and resource permissions.

## 7. Renew and finish {#renew}

### Renew a session proxy

With the recommended helper, renew in the same container and terminal with:

```bash
atlas_proxy
```

Without the helper, use the explicit commands below. Renew at the same filename so tools already configured with that path can use it:

```bash
if [[ -n ${X509_USER_PROXY:-} && -d ${ATLAS_PROXY_DIR:-} ]]; then
    voms-proxy-init \
        -voms atlas -valid 12:00 \
        -cert "$HOME/.globus/usercert.pem" \
        -key "$HOME/.globus/userkey.pem" \
        -out "$X509_USER_PROXY" \
    && voms-proxy-info -file "$X509_USER_PROXY" -timeleft
else
    echo 'Create a new session proxy using the earlier recipe.' >&2
fi
```

Restart clients that retain an expired credential in memory. For Codex, follow its [renew/resume instructions](../codex-agents/#sessions).

### Renew the personal certificate

Renew through your certificate authority before the personal certificate expires. Install the new certificate **and its matching private key**, check their validity, and confirm the certificate identity is still linked to your existing ATLAS IAM account. A changed subject or issuer may need a new link. Then create a fresh proxy. Certificate renewal, VO membership renewal, and proxy renewal are separate operations.

### Finish the session

After all clients using this proxy have finished:

```bash
voms-proxy-destroy -file "$X509_USER_PROXY" \
    && rmdir "$ATLAS_PROXY_DIR" \
    && unset X509_USER_PROXY ATLAS_PROXY_DIR
```

Keep the personal certificate and encrypted key for future sessions. Destroying this proxy removes the local copy; it does not revoke other credentials or tokens already issued.

## Troubleshooting {#troubleshooting}

### `No credentials found!`

Check `HOME`, filenames, and readability **inside the container**:

```bash
printf 'HOME=%s\n' "$HOME"
ls -l "$HOME/.globus/usercert.pem" "$HOME/.globus/userkey.pem"
```

Pass the paths explicitly with `-cert` and `-key`, as in the [creation recipe](#create-proxy). If the files are visible and the error remains, inspect preceding messages about loading or decrypting the key.

### `Error creating proxy certificate: : Invalid argument`

If VOMS reports a successful server contact followed by this error, check the output variable:

```bash
printf 'X509_USER_PROXY=<%s>\n' "${X509_USER_PROXY-UNSET}"
```

`<>` means the variable is set but empty; `<UNSET>` means it is absent. An empty exported value can make VOMS try to save to an invalid filename. Follow the [creation recipe](#create-proxy) to choose a private directory and pass a nonempty `-out` path. Do not derive the path from a failed `voms-proxy-info` invocation.

If it still fails with a valid, writable output path, add `-debug` to the `voms-proxy-init` command and inspect the final exception. The brief error alone is not enough to diagnose every possible failure.

### Other common problems

| Symptom | What to check |
| --- | --- |
| `atlas_proxy: command not found` | Install the helper once, then source `$HOME/.config/unity-atlas/atlas-proxy.sh` inside this container. The `.bashrc` source block defines it for shells that load that configuration. |
| `ATLAS_PROXY_DIR is not a private owned session directory` | Do not reuse that directory. Run `unset ATLAS_PROXY_DIR`, then invoke `atlas_proxy` to create a new private directory; the old file is not removed. |
| OpenSSL cannot read an older PKCS#12 bundle and reports an unsupported algorithm | Add `-legacy` to the affected `openssl pkcs12` extraction command. Keep encryption on the resulting PEM key. |
| Cannot decrypt the private key | Use the PEM passphrase chosen during conversion, which may differ from the bundle password. Check the file with `openssl pkey -check -noout`. |
| Browser does not offer the certificate or IAM does not show a link option | Import the personal certificate and its key, check expiry, and ensure the browser presents the intended certificate. Consult CERN's browser help if CA trust needs configuring. |
| VOMS rejects the identity or ATLAS attributes | Check certificate validity, approved VO membership, and the certificate link in ATLAS IAM. Newly approved changes can take time to propagate. |
| Proxy has disappeared or expired | Check its explicit filename and lifetime in the current container; recreate it on a new node or renew it at the existing path. |
| Rucio authenticates to an unexpected account | Check `RUCIO_ACCOUNT`; it is the ATLAS Rucio account, not automatically Unity `$USER`. |

If an instruction does not work, [open an issue](https://github.com/rafaellopesdesa/unity_atlas/issues) with the command, error, software version, and compute-node hostname. Omit private keys, proxy contents, passwords, and tokens.

## References {#references}

- CERN: [certificate authority](https://ca.cern.ch/ca/), [grid-user eligibility](https://ca.cern.ch/ca/Help/Default.aspx?kbid=021001), and [browser help](https://ca.cern.ch/ca/Help/?fdid=6).
- ATLAS: [obtaining a certificate](https://atlas-software.docs.cern.ch/analysis/analysis_tutorial/basicSetup/grid_cert/), [VO membership](https://atlas-software.docs.cern.ch/analysis/analysis_tutorial/basicSetup/grid_vo/), and [ATLAS IAM](https://atlas-auth.cern.ch/).
- US ATLAS: [joining the ATLAS VO](https://docs.sdcc.bnl.gov/experiments/usatlas/Joining_the_ATLAS_VO/).
- INDIGO IAM: [linking an X.509 certificate](https://indigo-iam.github.io/v/v1.15.0/docs/tasks/user/x509-linking/).
- OpenSSL: [PKCS#12 conversion](https://docs.openssl.org/3.0/man1/openssl-pkcs12/).
- VOMS: [client guide](https://italiangrid.github.io/voms/documentation/voms-clients-guide/3.0.2/) and [proxy-init manual](https://github.com/italiangrid/voms-clients/blob/main/man/voms-proxy-init.1.adoc).
- Rucio: [client authentication configuration](https://rucio.github.io/documentation/user/configuring_the_client/).

**Next:** [Submitting jobs with Slurm](../submitting-jobs/) runs ATLAS software on batch workers. [Codex Agents](../codex-agents/) uses your personal grid proxy for Rucio and AMI access.
