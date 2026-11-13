#!/usr/bin/env python3
"""Freeze a complete, closed Rucio dataset into one XRootD URL per file."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit


def checksum(value, field):
    if value is None:
        return None
    length = 8 if field == "adler32" else 32
    if not isinstance(value, str) or not re.fullmatch(rf"[0-9a-fA-F]{{{length}}}", value):
        raise ValueError(f"Invalid {field} checksum: {value!r}")
    return value.lower()


def file_record(item):
    size = item.get("bytes")
    if type(size) is not int or size < 0:
        raise ValueError(f"Missing or invalid file size for {item.get('name')}")
    if not all(isinstance(item.get(k), str) and item[k] for k in ("scope", "name")):
        raise ValueError("A file has no scope or name")
    return {"scope": item["scope"], "name": item["name"], "bytes": size,
            "adler32": checksum(item.get("adler32"), "adler32"),
            "md5": checksum(item.get("md5"), "md5")}


def list_files(client, scope, name):
    files = {}
    for item in client.list_files(scope, name):
        record = file_record(item)
        key = (record["scope"], record["name"])
        if key in files:
            raise ValueError(f"Duplicate file DID: {key[0]}:{key[1]}")
        files[key] = record
    if not files:
        raise ValueError("The dataset is empty")
    return files


def check_dataset(metadata, files=None):
    if str(metadata.get("type")).split(".")[-1] != "DATASET":
        raise ValueError("Use one DATASET DID; containers and files are not accepted")
    if metadata.get("open") is not False:
        raise ValueError("The dataset must be closed before creating a manifest")
    if files is not None:
        for field, expected in (("length", len(files)),
                                ("bytes", sum(f["bytes"] for f in files.values()))):
            if metadata.get(field) is not None and metadata[field] != expected:
                raise ValueError(f"Dataset {field} disagrees with its file listing")


def make_manifest(client, did, rse):
    scope, separator, name = did.partition(":")
    if not separator or not scope or not name:
        raise ValueError("Specify the dataset as scope:name")
    initial = client.get_did(scope, name)
    check_dataset(initial)
    expected = list_files(client, scope, name)
    check_dataset(initial, expected)
    keys = sorted(expected)
    selected = {}
    for start in range(0, len(keys), 1000):
        batch = [{"scope": s, "name": n} for s, n in keys[start:start + 1000]]
        for replica in client.list_replicas(
                batch, schemes=["root"], rse_expression=rse, domain="wan",
                all_states=False, ignore_availability=False, resolve_archives=False):
            record = file_record(replica)
            key = (record["scope"], record["name"])
            if key not in expected or key in selected:
                raise ValueError(f"Unexpected or repeated replica DID: {key}")
            if record["bytes"] != expected[key]["bytes"]:
                raise ValueError(f"Replica size disagrees with file listing: {key}")
            for field in ("adler32", "md5"):
                original = expected[key][field]
                if original is not None and record[field] not in (None, original):
                    raise ValueError(f"Replica {field} disagrees with file listing: {key}")
                record[field] = original if original is not None else record[field]
            # all_states=False requests AVAILABLE replicas; check returned states too.
            if "states" in replica and replica["states"].get(rse) != "AVAILABLE":
                raise ValueError(f"File is not AVAILABLE at {rse}: {key}")
            candidates = []
            for url, details in replica.get("pfns", {}).items():
                parsed = urlsplit(url)
                if (details.get("rse") == rse and parsed.scheme == "root"
                        and parsed.hostname and not details.get("client_extract", False)):
                    candidates.append((int(details.get("priority", 999999)), url))
            if not candidates:
                raise ValueError(f"No direct XRootD replica at {rse}: {key}")
            record["url"] = min(candidates)[1]
            selected[key] = record
    missing = set(expected) - set(selected)
    if missing:
        raise ValueError(f"{len(missing)} files have no available replica at {rse}")
    # Catch dataset membership changes during the catalogue queries.
    if list_files(client, scope, name) != expected:
        raise ValueError("Dataset file membership or metadata changed; retry later")
    check_dataset(client.get_did(scope, name), expected)
    return {"schema_version": 1, "did": did, "rse": rse,
            "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "files": [selected[key] for key in keys]}


def publish(manifest, output):
    """Publish atomically without replacing an existing manifest, including races."""
    output = Path(output)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=".manifest-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--did", required=True, help="One closed dataset, scope:name")
    parser.add_argument("--rse", default="NET2_LOCALGROUPDISK")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise FileExistsError(f"Refusing to replace {args.output}")
        from rucio.client import Client
        manifest = make_manifest(Client(), args.did, args.rse)
        publish(manifest, args.output)
        print(f"Saved {len(manifest['files'])} files to {args.output}")
    except Exception as error:
        print(f"Manifest not published: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
