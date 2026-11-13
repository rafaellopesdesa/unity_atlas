"""Exercise catalogue completeness and atomic publication without grid access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "examples/datasets/make-manifest.py"
SPEC = importlib.util.spec_from_file_location("dataset_manifest", SCRIPT)
manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manifest)
RSE = "NET2_LOCALGROUPDISK"


class Client:
    def __init__(self):
        self.metadata = {"type": "DATASET", "open": False, "length": 2, "bytes": 30}
        self.files = [{"scope": "mc", "name": "b", "bytes": 20, "adler32": None},
                      {"scope": "mc", "name": "a", "bytes": 10, "adler32": "ABCDEF01"}]
        self.replicas = []
        for item in self.files:
            replica = copy.deepcopy(item)
            replica.update(states={RSE: "AVAILABLE"}, pfns={
                f"root://host//{item['name']}": {"rse": RSE, "priority": 2},
                f"root://preferred//{item['name']}": {"rse": RSE, "priority": 1}})
            self.replicas.append(replica)
        self.calls = []
        self.changed_files = None
        self.file_calls = 0

    def get_did(self, scope, name):
        return copy.deepcopy(self.metadata)

    def list_files(self, scope, name):
        self.file_calls += 1
        source = self.changed_files if self.file_calls > 1 and self.changed_files is not None else self.files
        return iter(copy.deepcopy(source))

    def list_replicas(self, dids, **kwargs):
        self.calls.append((dids, kwargs))
        return iter(copy.deepcopy(self.replicas))


class ManifestTests(unittest.TestCase):
    def test_deterministic_complete_manifest(self):
        client = Client()
        result = manifest.make_manifest(client, "mc:dataset", RSE)
        self.assertEqual([f["name"] for f in result["files"]], ["a", "b"])
        self.assertEqual(result["files"][0]["url"], "root://preferred//a")
        self.assertEqual(result["files"][0]["adler32"], "abcdef01")
        self.assertIsNone(result["files"][0]["md5"])
        self.assertEqual(client.calls[0][1], dict(
            schemes=["root"], rse_expression=RSE, domain="wan", all_states=False,
            ignore_availability=False, resolve_archives=False))

    def test_missing_replica_is_not_a_partial_success(self):
        client = Client()
        client.replicas.pop()
        with self.assertRaisesRegex(ValueError, "no available replica"):
            manifest.make_manifest(client, "mc:dataset", RSE)

    def test_wrong_rse_and_unavailable_replica(self):
        for modification in ("rse", "state"):
            with self.subTest(modification=modification):
                client = Client()
                if modification == "rse":
                    for details in client.replicas[0]["pfns"].values():
                        details["rse"] = "OTHER"
                else:
                    client.replicas[0]["states"][RSE] = "COPYING"
                with self.assertRaises(ValueError):
                    manifest.make_manifest(client, "mc:dataset", RSE)

    def test_duplicate_file_or_replica_is_rejected(self):
        for collection in ("files", "replicas"):
            with self.subTest(collection=collection):
                client = Client()
                records = getattr(client, collection)
                records.append(copy.deepcopy(records[0]))
                with self.assertRaisesRegex(ValueError, "Duplicate|repeated"):
                    manifest.make_manifest(client, "mc:dataset", RSE)

    def test_only_closed_nonempty_datasets(self):
        for change in ("open", "container", "empty", "missing_open"):
            with self.subTest(change=change):
                client = Client()
                if change == "open":
                    client.metadata["open"] = True
                elif change == "container":
                    client.metadata["type"] = "CONTAINER"
                elif change == "missing_open":
                    del client.metadata["open"]
                else:
                    client.files = []
                with self.assertRaises(ValueError):
                    manifest.make_manifest(client, "mc:dataset", RSE)

    def test_changed_membership_or_size_or_checksum(self):
        for change in ("membership", "size", "checksum", "count"):
            with self.subTest(change=change):
                client = Client()
                if change == "membership":
                    client.changed_files = copy.deepcopy(client.files)
                    client.changed_files[0]["name"] = "new-file"
                elif change == "size":
                    client.replicas[0]["bytes"] = 999
                elif change == "checksum":
                    client.replicas[1]["adler32"] = "00000000"
                else:
                    client.metadata["length"] = 99
                with self.assertRaises(ValueError):
                    manifest.make_manifest(client, "mc:dataset", RSE)

    def test_publication_never_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            manifest.publish({"files": [1]}, output)
            self.assertEqual(json.loads(output.read_text()), {"files": [1]})
            with self.assertRaises(FileExistsError):
                manifest.publish({"files": [2]}, output)
            self.assertEqual(json.loads(output.read_text()), {"files": [1]})
            self.assertEqual(list(Path(directory).iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
