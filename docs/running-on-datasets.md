Run a local Unity Slurm array over an ATLAS dataset stored at **NET2_LOCALGROUPDISK**. Rucio arranges and protects the replica; the workers read its files directly through XRootD. No NFS mount or full dataset download to Unity is required.

Complete [Grid certificates and authentication](../grid-certificates/) and [Submitting jobs with Slurm](../submitting-jobs/) first. This chapter uses the environment chapter's `USER_PI`, `$USER`, `ATLAS_WORKDIR`, and shell shortcuts. Unity's PI directory follows `pi_[PI's username]`, for example `pi_rclsa_umass_edu`.

## 1. Choose a reproducible unit of work {#workflow}

The starting point is **one closed dataset, one frozen file manifest, and one file per array task**. Limit the number of simultaneous tasks and start with a single-file pilot. This keeps retries small and gives every input a stable output location.

| Stage | Where it runs | Result |
| --- | --- | --- |
| Request a replica | Interactive EL9 session with Rucio | A rule retaining one dataset copy at NET2. |
| Freeze the input list | The same authenticated session | `manifest.json`, with one available NET2 XRootD URL per file. |
| Submit | Fresh Unity Ubuntu login shell | A Slurm array with a concurrency limit. |
| Process | EL9 container on each worker | One validated histogram and completion receipt per input. |
| Check and retry | Unity login shell | A list of unfinished inputs, or a complete list for merging. |

The example reads a numeric branch and fills a ROOT histogram. It is an executable starting point for connecting your analysis to the workflow, not an ATLAS event selection. Later in the chapter we explain [how to replace it](#your-analysis).

## 2. Prepare a campaign directory {#prepare}

Use a new directory for each dataset/configuration/code version. Here the campaign name is `net2-susy15-v1`; replace it consistently if you choose another name. On the **Ubuntu login node**:

```bash
mkdir -p "$ATLAS_WORKDIR/jobs"
if mkdir "$ATLAS_WORKDIR/jobs/net2-susy15-v1"; then
    (
        set -e
        cd "$ATLAS_WORKDIR/jobs/net2-susy15-v1"
        mkdir logs
        for name in make-manifest.py atlas-dataset.sbatch run-dataset.sh \
                    analyse-file.py dataset_status.py; do
            curl --fail --location --output "$name" \
                "https://raw.githubusercontent.com/rafaellopesdesa/unity_atlas/main/examples/datasets/$name"
        done
    )
else
    echo 'Choose a new campaign name; the existing directory was not changed.' >&2
fi
```

Stop if directory creation or a download fails. Do not reuse a campaign containing old results. The five downloadable helpers are:

| Helper | Purpose |
| --- | --- |
| [make-manifest.py](../examples/datasets/make-manifest.py) | Check dataset completeness and select registered NET2 file URLs. |
| [atlas-dataset.sbatch](../examples/datasets/atlas-dataset.sbatch) | Allocate a worker and enter EL9. |
| [run-dataset.sh](../examples/datasets/run-dataset.sh) | Validate a worker proxy, load the release, and launch the analysis. |
| [analyse-file.py](../examples/datasets/analyse-file.py) | Read one file, validate the output, and publish its result atomically. |
| [dataset_status.py](../examples/datasets/dataset_status.py) | Validate results and produce retry or merge lists. |

Keep this directory on shared `/work/${USER_PI}/${USER}` storage. Slurm transfers the submission script, not the other files. Credentials will be stored separately in private shared home storage.

## 3. Request and retain the NET2 replica {#replicate}

Start an interactive EL9 session using the existing helpers:

```bash
# Unity login node
unity_cpu

# Allocated Ubuntu compute node
module load apptainer/latest
cd "$ATLAS_WORKDIR/jobs/net2-susy15-v1"
setupATLAS -c el9
```

Inside EL9, use the grid chapter's recommended [`atlas_proxy` shortcut](../grid-certificates/#proxy-helper). It supplies the explicit certificate/key and proxy output paths. Install the helper once as described there; sourcing its file below also works when the container has not loaded your `.bashrc`.

Set your ATLAS Rucio account; it may differ from Unity's `$USER`. The example DID below is a concrete SUSY15 dataset; replace it when processing another dataset:

```bash
cd "$ATLAS_WORKDIR/jobs/net2-susy15-v1"
lsetup rucio
source "$HOME/.config/unity-atlas/atlas-proxy.sh"
atlas_proxy
```

Continue only if `atlas_proxy` succeeds. The explicit [manual proxy recipe](../grid-certificates/#create-proxy) remains available if you have not installed the shortcut. Then configure Rucio and the dataset:

```bash
export RUCIO_ACCOUNT=YOUR_RUCIO_ACCOUNT
export RUCIO_AUTH_TYPE=x509_proxy
export RSE=NET2_LOCALGROUPDISK
DID='mc16_13TeV:mc16_13TeV.501261.MGPy8EG_s0zpzp2mu2e_500_100_10.deriv.DAOD_SUSY15.e8092_e7400_s3126_r11891_r11748_p4800_tid27118280_00'

rucio --version
rucio rse list --rses "$RSE"
rucio did show "$DID"
rucio rule list --did "$DID"
```

Use the **full dataset DID**, including scope, not a filename or an XRootD URL. This is the dataset containing the example file `DAOD_SUSY15.27118280._000001.pool.root.1`; the manifest will include all of its files. Still check its current replica and rule state before requesting another transfer. A dataset is a set of files; a container is a set of datasets. For a container, inspect its contents with `rucio did content list "$CONTAINER_DID"`, choose its closed child datasets, and use a separate campaign for each. Do not close an official production dataset yourself; wait for completion or select a closed dataset.

Check existing rules before creating another one. An existing rule that retains this dataset at NET2 for your whole campaign may be sufficient. Otherwise request **one copy** at this exact RSE, for example for 14 days:

```bash
rucio rule add --copies 1 --rses "$RSE" --lifetime 1209600 "$DID"
```

Record the returned rule ID. This schedules a site-to-site transfer; it does not download the dataset to Unity. The example lifetime is in seconds and must cover the transfer, queueing, processing, and retries. It is not a statement of NET2 quota or retention policy.

```bash
read -r -p 'Rule ID to monitor: ' RULE_ID
printf '%s\n' "$RULE_ID" > rule-id.txt
rucio rule show "$RULE_ID"
```

Continue when the rule is **OK** and all file locks are satisfied. A rule ID alone is not evidence that the transfer has finished. If it is stuck, use `rucio rule show --examine "$RULE_ID"` and contact the relevant support team with the rule ID. Do not submit repeated rules to retry the same transfer. You can leave the allocation while waiting and return in a later authenticated session.

ATLAS membership permitting reads does not automatically grant your Rucio account quota or permission to place data at this RSE. If the request is rejected, ask the NET2 storage contact for the appropriate quota, group account, or approval procedure. Do not change accounts or request approval flags without knowing the site's policy. Files present without a protecting rule can later be deleted by Rucio.

### Older Rucio clients

The commands above use the newer grouped CLI. If the client supplied by `lsetup rucio` does not recognize it, use the equivalent legacy command below. Run **one form**, not both:

| Newer command | Legacy equivalent |
| --- | --- |
| `rucio rse list --rses "$RSE"` | `rucio list-rses --rses "$RSE"` |
| `rucio did show "$DID"` | `rucio stat "$DID"` |
| `rucio did content list "$CONTAINER_DID"` | `rucio list-content "$CONTAINER_DID"` |
| `rucio rule list --did "$DID"` | `rucio list-rules "$DID"` |
| `rucio rule add --copies 1 --rses "$RSE" --lifetime 1209600 "$DID"` | `rucio add-rule --lifetime 1209600 "$DID" 1 "$RSE"` |
| `rucio rule show "$RULE_ID"` | `rucio rule-info "$RULE_ID"` |
| `rucio rule show --examine "$RULE_ID"` | `rucio rule-info --examine "$RULE_ID"` |

## 4. Freeze a complete input manifest {#manifest}

Still inside EL9 with `lsetup rucio` and a valid proxy, run:

```bash
python make-manifest.py --did "$DID" --rse "$RSE" --output manifest.json
```

The helper uses Rucio's Python client instead of parsing a printed table. It:

- Requires a closed, nonempty dataset and independently lists **all** its files.
- Queries available, directly readable `root://` replicas at `NET2_LOCALGROUPDISK`, respecting the RSE's read-availability setting.
- Selects exactly one registered URL per file, sorts by file DID, and records scope, name, size, and catalogue checksums.
- Refuses duplicates, missing replicas, inconsistent metadata, or a changed dataset listing. A partial transfer cannot silently become a partial analysis.
- Publishes `manifest.json` only when complete, and refuses to overwrite an existing manifest.

Inspect the snapshot and optionally export a simple URL list for other tools:

```bash
python - <<'PY'
import json
with open('manifest.json') as stream:
    manifest = json.load(stream)
files = manifest['files']
print('Dataset:', manifest['did'])
print('RSE:', manifest['rse'])
print('Files:', len(files))
print('Total size: %.3f GB' % (sum(f['bytes'] for f in files) / 1e9))
print('First URL:', files[0]['url'])
with open('inputs.txt', 'x') as stream:
    stream.writelines(f['url'] + '\n' for f in files)
PY
```

The Slurm example uses `manifest.json`, which preserves more information than `inputs.txt`. Catalogue availability is checked at preparation time; worker reads can still fail later, which is why output validation and retries remain necessary. Stored catalogue checksums are provenance; selective ROOT reads do not recompute a whole-file checksum.

**Use the URLs Rucio returns.** Do not reconstruct hashed `/rucio/...` directories or replace hostnames with string substitutions. `root://xrootd.data.net2.mghpcc.org:1094//atlaslocalgroupdisk/...` is a NET2 access pattern, but the manifest must follow the registered read endpoints. If those endpoints are inaccessible from a worker, resolve that with NET2/Rucio configuration before scaling up.

## 5. Make the proxy available to workers {#worker-proxy}

The grid chapter's `/tmp` proxy belongs to its node/container. A batch worker cannot access it merely because its path was exported. Copy the valid proxy to a **private shared-home directory**, outside the campaign. Run this in the authenticated EL9 session, from the campaign directory:

```bash
PROXY_REL=".globus/unity-atlas-proxies/$(basename "$PWD")/x509up"
PROXY_DIR="$HOME/$(dirname "$PROXY_REL")"
umask 077
mkdir -p "$PROXY_DIR"
chmod 700 "$HOME/.globus" "$HOME/.globus/unity-atlas-proxies" "$PROXY_DIR"

if PROXY_NEW=$(mktemp "$PROXY_DIR/.x509up.XXXXXXXX"); then
    if cp -- "$X509_USER_PROXY" "$PROXY_NEW" \
        && chmod 600 "$PROXY_NEW" \
        && voms-proxy-info -file "$PROXY_NEW" -exists \
        && voms-proxy-info -file "$PROXY_NEW" -acexists atlas \
        && voms-proxy-info -file "$PROXY_NEW" -all; then
        mv -f -- "$PROXY_NEW" "$HOME/$PROXY_REL"
    else
        rm -f -- "$PROXY_NEW"
        echo 'Proxy was not published; fix authentication before submitting.' >&2
    fi
fi
```

Inspect **both** the proxy and VOMS-attribute lifetimes. Each worker requires enough remaining validity for its requested wall time plus 15 minutes. The default two-hour job therefore needs more than 2 hours 15 minutes remaining **when it starts**, after queueing.

The batch wrapper passes the relative proxy path explicitly because it uses `--export=NONE`. Inside EL9, the payload resolves it against that container's `$HOME`, copies it into a private worker `/tmp` directory, and validates the copy. It needs no private key, password prompt, or Rucio dataset query. It preserves the grid CA certificate-directory setting while keeping grid-tool Python and library setup separate from the analysis release.

For renewal, run `atlas_proxy` again in an authenticated EL9 session, then repeat the copy block above from the same campaign directory only after it succeeds. The [grid chapter](../grid-certificates/#renew) also gives the manual commands. The temporary-file rename updates the shared source atomically. **Queued tasks can use the replacement; already-running tasks keep their original copy.** Do not request a wall time longer than the credential can cover, and do not extend a running job beyond its validated proxy lifetime.

Leave the container and allocation with `exit` twice. The remaining preparation and `sbatch` commands run in a **fresh Ubuntu login shell**.

## 6. Configure and freeze the analysis {#configure}

```bash
cd "$ATLAS_WORKDIR/jobs/net2-susy15-v1"
read -r -p 'ATLAS project,exact-version: ' ATLAS_RELEASE
read -r -p 'Numeric branch (for example MuonsAuxDyn.pt): ' ATLAS_BRANCH

python3 - "$ATLAS_RELEASE" "$ATLAS_BRANCH" <<'PY'
import json
import sys
config = dict(release=sys.argv[1], tree='CollectionTree', branch=sys.argv[2],
              bins=100, xmin=0.0, xmax=200000.0)
with open('analysis-config.json', 'x') as stream:
    json.dump(config, stream, indent=2)
    stream.write('\n')
PY
```

Choose the exact release that supports your input and analysis. `MuonsAuxDyn.pt` is an example, not a promise that every DAOD has that branch; inspect your file's schema and select an existing numeric scalar/vector branch. Adjust the tree name and histogram range in `analysis-config.json` before freezing it. The example range is suitable for a momentum expressed in MeV.

The Python analysis opens the file, checks its size against the manifest, books a histogram and an event count, and runs the event loop over the selected branch. It checks the processed event count and reopens the output before publishing it. It does not treat a metadata-only file open as successful analysis.

Freeze the input list, configuration, and code together:

```bash
sha256sum manifest.json analysis-config.json make-manifest.py \
    atlas-dataset.sbatch run-dataset.sh analyse-file.py dataset_status.py \
    > campaign.sha256
sha256sum --check --strict campaign.sha256
```

Do not edit these files or regenerate this checksum list while jobs are queued, running, or being retried. Both host and container check it. For a new analysis version, create a new campaign directory; keep the original manifest and results as provenance. `logs/` must already exist before submission.

## 7. Run one task, then scale out {#submit}

From the **Ubuntu login shell**, submit a pilot for manifest index zero:

```bash
PROXY_REL=".globus/unity-atlas-proxies/$(basename "$PWD")/x509up"
if PILOT_ID=$(sbatch --parsable --array=0 atlas-dataset.sbatch "$USER_PI" "$PROXY_REL"); then
    PILOT_ID=${PILOT_ID%%;*}
    printf 'Pilot job: %s\n' "$PILOT_ID"
fi
```

The defaults are one CPU, 4 GB, and two hours per task. Wait for completion and inspect:

```bash
squeue --jobs="$PILOT_ID"
sacct --jobs="$PILOT_ID" --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -n 50 "logs/atlas-dataset-${PILOT_ID}_0.out"
tail -n 50 "logs/atlas-dataset-${PILOT_ID}_0.err"
python3 dataset_status.py --campaign "$PWD"
```

The status tool reports `1/N` complete after a successful pilot and returns nonzero while the whole dataset is unfinished. Inspect `results/task-000000/result.root` and `receipt.json`, and require Slurm `COMPLETED` with exit code `0:0`. If configuration or analysis code needs changing, make a fresh campaign before launching the dataset. Adjust resources based on the pilot's time and memory, not on the bulk-transfer rate alone.

Get the file count and inspect the cluster's array limits:

```bash
NFILES=$(python3 -c 'import json; print(len(json.load(open("manifest.json"))["files"]))')
scontrol show config | grep -E 'MaxArraySize|SchedulerParameters'
printf 'Dataset has %s tasks\n' "$NFILES"
```

`MaxArraySize` limits the highest array index, and site policy can also limit task counts and submitted jobs. If the dataset fits those limits, submit with at most **four simultaneous tasks** initially:

```bash
if JOB_ID=$(sbatch --parsable --array="0-$((NFILES-1))%4" \
    atlas-dataset.sbatch "$USER_PI" "$PROXY_REL"); then
    JOB_ID=${JOB_ID%%;*}
    printf 'Dataset array: %s\n' "$JOB_ID"
fi
```

The completed pilot result is validated and reused rather than counted twice. A task publishes to `results/task-INDEX/` only after its temporary output and receipt pass validation. Retries use the same manifest index. Interrupted temporary directories do not count as completed inputs.

Use command-line options such as `--cpus-per-task=4 --mem=8G --time=01:00:00` to override resources. The sample enables ROOT threading only up to the CPU allocation. Increase `%4` gradually after measuring event throughput, memory, and the effect of concurrent readers. A fast single-file transfer does not establish the capacity available to every simultaneous job.

### Datasets larger than one array

The optional third script argument is a **manifest offset**. For example, a second window of 500 files uses local array indices `0-499` and offset `500`, which process manifest indices `500-999`:

```bash
# Example only: requires at least 1000 files and a site limit permitting 500 tasks.
sbatch --array=0-499%4 atlas-dataset.sbatch "$USER_PI" "$PROXY_REL" 500
```

Submit only windows within the manifest, shorten the final window, and finish one window before submitting the next if you want a global concurrency limit of four. `%4` is a limit **per array**, not across all your arrays. Global manifest indices remain stable even though Slurm indices restart at zero.

## 8. Check completeness, retry, and merge {#results}

Monitor arrays with `squeue` and `sacct` as above. After the relevant arrays have stopped, validate the published results:

```bash
python3 dataset_status.py --campaign "$PWD" --retry-list retry-1.txt
```

The helper checks every expected input, its code/configuration hashes, event counts, and the output's size and SHA-256. It returns nonzero for unfinished or invalid results and writes their manifest indices to `retry-1.txt`. It refuses to overwrite old lists; use `retry-2.txt` for a later pass. A Slurm success flag or the mere existence of a ROOT file is insufficient.

Inspect the failures, renew the shared proxy if needed, and fix operational causes before retrying. For a dataset using a single zero-offset array:

```bash
RETRY=$(cat retry-1.txt)
if [[ -n "$RETRY" ]]; then
    sbatch --array="${RETRY}%4" atlas-dataset.sbatch "$USER_PI" "$PROXY_REL"
fi
```

For offset windows, the retry list contains **global** manifest indices, including files in future windows that have not run yet. First select only indices belonging to the window you are retrying, then subtract its offset to obtain local Slurm indices and pass that offset again. For example, global index `507` is `--array=7` with offset `500`. Keep retry arrays within the same site limits.

A published result that fails validation is deliberately not overwritten. With its tasks stopped, preserve it under a separate `quarantine/` directory before retrying that index. Do not delete a valid result to force a rerun; changed analysis code belongs in a new campaign.

Only when every file has a valid result should you produce the merge list:

```bash
python3 dataset_status.py --campaign "$PWD" --outputs outputs.txt
```

If anything is incomplete, no new merge list is written. The list contains exactly one result per input, in manifest order. Do not collect outputs with a broad wildcard over original jobs, retries, and temporary directories.

For the example histograms, merge **inside an allocated EL9 session with the same release**. Revalidate the complete manifest and merge those exact outputs, avoiding shell argument-length limits. Publish the merged file only after success:

```bash
cd "$ATLAS_WORKDIR/jobs/net2-susy15-v1"
ATLAS_RELEASE=$(python3 -c 'import json; print(json.load(open("analysis-config.json"))["release"])')
asetup "$ATLAS_RELEASE"
python - <<'PY'
from pathlib import Path
import os
import tempfile
import ROOT
from dataset_status import load_campaign, inspect_campaign

campaign = load_campaign('.')
outputs, failures = inspect_campaign(campaign)
if failures:
    raise RuntimeError('Dataset incomplete; do not merge')
target = Path('merged.root')
if target.exists():
    raise RuntimeError('merged.root already exists; preserve the previous merge')
with tempfile.TemporaryDirectory(prefix='.merge-', dir='.') as directory:
    temporary = Path(directory) / 'merged.root'
    merger = ROOT.TFileMerger()
    if not merger.OutputFile(str(temporary), 'RECREATE'):
        raise RuntimeError('Cannot create merge output')
    for output in outputs:
        if not merger.AddFile(str(output)):
            raise RuntimeError(f'Cannot add {output}')
    if not merger.Merge():
        raise RuntimeError('Merge failed')
    del merger
    check = ROOT.TFile.Open(str(temporary), 'READ')
    if not check or check.IsZombie() or not check.Get('example'):
        raise RuntimeError('Merged histogram is missing or unreadable')
    check.Close()
    os.link(temporary, target)  # Atomic publication; refuses an existing target.
print('Merged', len(outputs), 'validated inputs into', target)
PY
```

This merges the example's histogram outputs, **not the original xAOD/DAOD files**. Use your analysis framework's merge and metadata checks for other output formats. Preserve `manifest.json`, configuration, code, receipts, and job IDs alongside the final result. Move durable results to your `/project/${USER_PI}/${USER}` area according to Unity storage policy.

When all queued/running tasks and retries have finished, destroy the campaign's shared proxy from an EL9 session with `lsetup rucio`:

```bash
PROXY_REL=".globus/unity-atlas-proxies/$(basename "$PWD")/x509up"
voms-proxy-destroy -file "$HOME/$PROXY_REL"
```

Keep the Rucio rule alive through processing and recovery. In an authenticated Rucio session, reload its ID with `RULE_ID=$(cat rule-id.txt)`. If you own it and need more time, use `rucio rule update --lifetime 1209600 "$RULE_ID"` (legacy: `rucio update-rule --lifetime 1209600 "$RULE_ID"`), subject to policy. Do not delete rules owned by someone else or remove replicas directly from dCache.

## 9. Adapt the example to your analysis {#your-analysis}

Replace the histogram computation in `analyse-file.py` before freezing a new campaign. The selected input is `campaign.manifest['files'][index]['url']`; pass that URL to ROOT, uproot, or your ATLAS analysis executable. Keep the following behavior:

- A read failure produces a nonzero exit; never silently skip a file.
- Output is written into the supplied temporary `staging` directory and validated before publication.
- The receipt identifies the input and exact configuration/code, and records a meaningful completeness check for your analysis. After event selections, distinguish events processed from events selected.
- Any extra scripts, configuration, or compiled-build identity are included in `campaign.sha256` and the receipt's provenance checks. The example's `INPUTS` list is in `dataset_status.py`.

The starting granularity is one file per task. If files are tiny compared with container/release startup time, group several files into a task in a later version and record/check every member. If one file exceeds the credential or wall-time budget, use explicit nonoverlapping event ranges and validate total coverage. Keep these partitions fixed for retries.

Direct XRootD reads avoid a second full copy in Unity storage. If measurements show that repeated scans benefit from staging, download into job-local scratch, verify the catalogue checksum, and account for local capacity and cleanup. Keep dataset discovery out of each worker: catalogue queries are done once when preparing the manifest.

## Troubleshooting {#troubleshooting}

| Symptom | What to check |
| --- | --- |
| Rucio rejects the rule | Exact RSE name, account quota, write permission, and site approval policy. |
| Rule remains replicating or stuck | Inspect the rule and transfer errors; do not start from an incomplete URL list. |
| Manifest creation fails | Closed DATASET rather than container, all files available, direct ROOT protocol, and readable RSE status. Existing manifests are never replaced. |
| Worker cannot find the proxy | Copy it into private shared home and pass the relative path; the interactive `/tmp` filename is not shared. |
| Proxy expires too soon | Renew and atomically republish the shared source, then retry; running tasks keep their original snapshot. |
| `campaign.sha256` fails | A frozen input changed or is missing. Restore it or create a new campaign rather than mixing versions. |
| ROOT branch/type error | Inspect the actual DAOD schema and use a supported numeric branch and compatible release. |
| Some tasks time out or run out of memory | Use their logs and accounting to adjust resources; do not mark them successful. |
| Existing published result is invalid | Stop its tasks, preserve the directory in quarantine, investigate, then retry. |
| Array rejected | Check index/task/submission limits; use bounded windows with explicit offsets. |
| All jobs completed, but the status tool reports missing inputs | Check failed/retried tasks and manifest indices; do not merge until complete. |

If an instruction does not work, [open an issue](https://github.com/rafaellopesdesa/unity_atlas/issues) with the command, error, client/release versions, node hostname, and relevant task or rule ID. Omit proxy contents, private keys, and tokens.

## References {#references}

- Rucio: [replication rules](https://rucio.github.io/documentation/started/concepts/replica_management/), [current CLI examples](https://rucio.github.io/documentation/started/concepts/replication_rules_examples/), [DID client](https://rucio.github.io/documentation/html/client_api/didclient.html), and [replica client](https://rucio.github.io/documentation/html/client_api/replicaclient.html).
- Rucio CLI definitions: [rules](https://github.com/rucio/rucio/blob/master/lib/rucio/cli/rule.py) and [replicas](https://github.com/rucio/rucio/blob/master/lib/rucio/cli/replica.py).
- Unity: [batch jobs](https://docs.unity.rc.umass.edu/documentation/jobs/sbatch/) and [storage](https://docs.unity.rc.umass.edu/documentation/cluster_specs/storage/).
- Slurm: [job arrays](https://slurm.schedmd.com/job_array.html) and [sbatch](https://slurm.schedmd.com/sbatch.html).
- ROOT: [RDataFrame](https://root.cern.ch/doc/master/classROOT_1_1RDataFrame.html) and [TFileMerger](https://root.cern.ch/doc/master/classTFileMerger.html).

**Next:** [Using Pixi](../using-pixi/) covers personal tools and project package environments.
