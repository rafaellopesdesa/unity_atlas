#!/usr/bin/env python3
"""Read one complete ROOT tree and publish a checked histogram and provenance receipt.

Replace the histogram computation with your analysis, retaining failure propagation,
appropriate completeness checks, and atomic publication. Never skip unreadable input.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile

from dataset_status import load_campaign, publish_result, sha256, validate_result


def analyse(campaign, index, cpus, staging):
    import ROOT

    ROOT.gROOT.SetBatch(True)
    ROOT.DisableImplicitMT()
    if cpus > 1:
        ROOT.EnableImplicitMT(cpus)
    config = campaign.config
    item = campaign.manifest["files"][index]
    source = ROOT.TFile.Open(item["url"], "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"Cannot open input: {item['url']}")
    try:
        if source.GetSize() != item["bytes"]:
            raise RuntimeError("Input size differs from the frozen Rucio manifest")
        tree = source.Get(config["tree"])
        if not tree or not tree.InheritsFrom("TTree"):
            raise RuntimeError(f"Missing TTree: {config['tree']}")
        expected = int(tree.GetEntries())
    finally:
        source.Close()
    # Let RDF own its input handles instead of borrowing the metadata TTree.
    frame = ROOT.RDataFrame(config["tree"], item["url"])
    if config["branch"] not in {str(name) for name in frame.GetColumnNames()}:
        raise RuntimeError(f"Branch not found: {config['branch']}; inspect this DAOD's schema")
    # Book both actions before triggering the event loop. The histogram forces
    # branch data to be read; Count alone is not a throughput benchmark.
    histogram = frame.Histo1D(("example", "Dataset example;value;Entries", config["bins"],
                              config["xmin"], config["xmax"]), config["branch"])
    count = frame.Count()
    histogram.GetValue()
    processed = int(count.GetValue())
    if processed != expected:
        raise RuntimeError(f"Processed {processed} of {expected} input events")
    destination = ROOT.TFile.Open(str(staging / "result.root"), "RECREATE")
    if not destination or destination.IsZombie():
        raise RuntimeError("Cannot create output ROOT file")
    try:
        destination.cd()
        if histogram.GetValue().Write("example") <= 0:
            raise RuntimeError("Failed to write the histogram")
    finally:
        destination.Close()
    check = ROOT.TFile.Open(str(staging / "result.root"), "READ")
    if not check or check.IsZombie():
        raise RuntimeError("Cannot reopen the output ROOT file")
    try:
        saved = check.Get("example")
        if not saved or not saved.InheritsFrom("TH1"):
            raise RuntimeError("Output histogram is missing")
    finally:
        check.Close()
    output = staging / "result.root"
    receipt = {"schema_version": 1, "index": index, "input": item,
               "inputs_sha256": campaign.hashes, "release": config["release"],
               "tree": config["tree"], "branch": config["branch"],
               "expected_events": expected, "processed_events": processed,
               "output_bytes": output.stat().st_size, "output_sha256": sha256(output),
               "completed_utc": datetime.now(timezone.utc).isoformat(),
               "root_version": ROOT.gROOT.GetVersion(), "cpus": cpus}
    (staging / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--index", required=True, type=int)
    parser.add_argument("--cpus", type=int, default=1)
    args = parser.parse_args()
    if args.cpus < 1:
        parser.error("--cpus must be positive")
    campaign = load_campaign(args.campaign)
    if not 0 <= args.index < len(campaign.manifest["files"]):
        parser.error("--index is outside the manifest")
    final = campaign.result_dir(args.index)
    if final.exists():
        validate_result(campaign, args.index)
        print(f"Task {args.index}: valid result already exists; nothing repeated.")
        return
    final.parent.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".task-{args.index:06d}-", dir=final.parent))
    try:
        analyse(campaign, args.index, args.cpus, staging)
        publish_result(campaign, args.index, staging)
        print(f"Task {args.index}: complete, {final / 'result.root'}")
    finally:
        # Only this attempt's temporary directory is removed. SIGKILL may leave
        # it behind; collectors ignore these hidden directories.
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == "__main__":
    main()
