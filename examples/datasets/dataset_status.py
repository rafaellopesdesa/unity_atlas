#!/usr/bin/env python3
"""Validate one published result per manifest file; never merge partial attempts."""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile


INPUTS = ("manifest.json", "analysis-config.json", "make-manifest.py", "analyse-file.py",
          "dataset_status.py", "run-dataset.sh", "atlas-dataset.sbatch")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class Campaign:
    root: Path
    manifest: dict
    config: dict
    hashes: dict

    def result_dir(self, index):
        return self.root / "results" / f"task-{index:06d}"


def load_campaign(directory):
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    config = json.loads((root / "analysis-config.json").read_text())
    if manifest.get("schema_version") != 1 or not manifest.get("files"):
        raise ValueError("Expected a nonempty version-1 manifest")
    identities = set()
    for item in manifest["files"]:
        identity = (item["scope"], item["name"])
        if identity in identities:
            raise ValueError(f"Duplicate input DID: {identity}")
        identities.add(identity)
        if not item["url"].startswith("root://") or int(item["bytes"]) <= 0:
            raise ValueError(f"Invalid ROOT URL or file size: {identity}")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*,[0-9][A-Za-z0-9_.-]*", config["release"]):
        raise ValueError("Set release to an exact project,version, e.g. your AnalysisBase release")
    if not config["tree"] or not config["branch"]:
        raise ValueError("Specify the tree and numeric branch to read")
    if type(config["bins"]) is not int or config["bins"] <= 0:
        raise ValueError("bins must be a positive integer")
    if not all(math.isfinite(config[k]) for k in ("xmin", "xmax")) or config["xmin"] >= config["xmax"]:
        raise ValueError("Specify finite histogram limits with xmin < xmax")
    return Campaign(root, manifest, config, {name: sha256(root / name) for name in INPUTS})


def validate_result(campaign, index, directory=None):
    """Raise on an absent, incomplete, changed, or mismatched result."""
    directory = Path(directory) if directory is not None else campaign.result_dir(index)
    receipt = json.loads((directory / "receipt.json").read_text())
    item = campaign.manifest["files"][index]
    expected = {"schema_version": 1, "index": index, "input": item,
                "inputs_sha256": campaign.hashes, "release": campaign.config["release"],
                "tree": campaign.config["tree"], "branch": campaign.config["branch"]}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Receipt does not match this input, configuration, or code")
    events = receipt.get("expected_events")
    if type(events) is not int or events < 0 or receipt.get("processed_events") != events:
        raise ValueError("Incomplete event processing")
    output = directory / "result.root"
    size = output.stat().st_size
    if size <= 0 or receipt.get("output_bytes") != size or receipt.get("output_sha256") != sha256(output):
        raise ValueError("Output is missing, truncated, or changed")
    return receipt


def publish_result(campaign, index, staging):
    """Atomically expose a validated directory; a simultaneous valid winner is reused."""
    staging = Path(staging)
    validate_result(campaign, index, staging)
    final = campaign.result_dir(index)
    if final.exists():
        validate_result(campaign, index)
        shutil.rmtree(staging)
        return False
    try:
        staging.rename(final)
    except OSError:
        if not final.exists():
            raise
        validate_result(campaign, index)
        shutil.rmtree(staging)
        return False
    return True


def write_new(path, content):
    """Publish a complete list without replacing an older list."""
    path = Path(path).resolve()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def inspect_campaign(campaign):
    complete, failures = [], []
    for index in range(len(campaign.manifest["files"])):
        try:
            validate_result(campaign, index)
            complete.append(campaign.result_dir(index) / "result.root")
        except (OSError, ValueError, KeyError, TypeError) as error:
            failures.append((index, str(error)))
    return complete, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--retry-list", help="Write comma-separated unfinished indices to a NEW file")
    parser.add_argument("--outputs", help="Write a NEW merge list only when every input is complete")
    args = parser.parse_args()
    campaign = load_campaign(args.campaign)
    complete, failures = inspect_campaign(campaign)
    print(f"Complete: {len(complete)}/{len(campaign.manifest['files'])}; unfinished: {len(failures)}")
    for index, reason in failures[:10]:
        print(f"  Task {index}: {reason}")
    if len(failures) > 10:
        print("  Further unfinished indices are included in --retry-list.")
    if args.retry_list:
        write_new(args.retry_list, ",".join(str(index) for index, _ in failures) + ("\n" if failures else ""))
    if args.outputs:
        if failures:
            print("No merge list written: the dataset is incomplete.")
        else:
            write_new(args.outputs, "".join(f"{path}\n" for path in complete))
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"ERROR: {error}")
