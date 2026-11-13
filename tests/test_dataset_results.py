"""Exercise result integrity and publication without ROOT or grid credentials."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "examples/datasets/dataset_status.py"
SPEC = importlib.util.spec_from_file_location("dataset_status", MODULE_PATH)
status = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = status
SPEC.loader.exec_module(status)
ANALYSIS_SPEC = importlib.util.spec_from_file_location("analyse_file", MODULE_PATH.with_name("analyse-file.py"))
analysis = importlib.util.module_from_spec(ANALYSIS_SPEC)
ANALYSIS_SPEC.loader.exec_module(analysis)


class DatasetResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in status.INPUTS:
            (self.root / name).write_text("unchanged example code\n")
        self.manifest = {"schema_version": 1, "did": "scope:dataset", "rse": "NET2_LOCALGROUPDISK",
                         "files": [{"scope": "scope", "name": f"file-{i}", "bytes": 123,
                                    "adler32": "12345678", "md5": None,
                                    "url": f"root://host//file-{i}"} for i in range(2)]}
        self.config = {"release": "AnalysisBase,25.2.1", "tree": "CollectionTree",
                       "branch": "MuonsAuxDyn.pt", "bins": 100, "xmin": 0, "xmax": 200000}
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        (self.root / "analysis-config.json").write_text(json.dumps(self.config))
        (self.root / "results").mkdir()
        self.campaign = status.load_campaign(self.root)

    def staging(self, index, content=b"pretend valid ROOT output"):
        path = Path(tempfile.mkdtemp(prefix=".task-attempt-", dir=self.root / "results"))
        output = path / "result.root"
        output.write_bytes(content)
        receipt = {"schema_version": 1, "index": index, "input": self.manifest["files"][index],
                   "inputs_sha256": self.campaign.hashes, "release": self.config["release"],
                   "tree": self.config["tree"], "branch": self.config["branch"],
                   "expected_events": 12, "processed_events": 12,
                   "output_bytes": len(content), "output_sha256": status.sha256(output)}
        (path / "receipt.json").write_text(json.dumps(receipt))
        return path

    def cli(self, *args):
        with patch.object(sys, "argv", ["dataset_status.py", "--campaign", str(self.root), *args]):
            with contextlib.redirect_stdout(io.StringIO()):
                return status.main()

    def test_missing_outputs_and_hidden_attempts_never_count(self):
        self.staging(0)
        complete, failures = status.inspect_campaign(self.campaign)
        self.assertEqual(complete, [])
        self.assertEqual([i for i, _ in failures], [0, 1])

    def test_publish_and_repeat_produce_only_one_result(self):
        attempt = self.staging(0)
        self.assertTrue(status.publish_result(self.campaign, 0, attempt))
        self.assertFalse(attempt.exists())
        duplicate = self.staging(0)
        self.assertFalse(status.publish_result(self.campaign, 0, duplicate))
        complete, failures = status.inspect_campaign(self.campaign)
        self.assertEqual(len(complete), 1)
        self.assertEqual([i for i, _ in failures], [1])

    def test_publish_race_reuses_valid_winner(self):
        attempt, winner = self.staging(0), self.staging(0)
        original_rename = Path.rename

        def competing_rename(source, target):
            original_rename(winner, target)
            raise FileExistsError("another worker won")

        with patch.object(Path, "rename", competing_rename):
            self.assertFalse(status.publish_result(self.campaign, 0, attempt))
        status.validate_result(self.campaign, 0)
        self.assertFalse(attempt.exists())

    def test_changed_output_detected_even_when_size_matches(self):
        status.publish_result(self.campaign, 0, self.staging(0, b"original"))
        (self.campaign.result_dir(0) / "result.root").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "changed"):
            status.validate_result(self.campaign, 0)

    def test_changed_configuration_invalidates_old_results(self):
        status.publish_result(self.campaign, 0, self.staging(0))
        self.config["branch"] = "ElectronsAuxDyn.pt"
        (self.root / "analysis-config.json").write_text(json.dumps(self.config))
        changed = status.load_campaign(self.root)
        with self.assertRaisesRegex(ValueError, "configuration"):
            status.validate_result(changed, 0)

    def test_existing_invalid_result_is_preserved(self):
        final = self.campaign.result_dir(0)
        final.mkdir()
        (final / "result.root").write_bytes(b"do not overwrite")
        with self.assertRaises(OSError):
            status.publish_result(self.campaign, 0, self.staging(0))
        self.assertEqual((final / "result.root").read_bytes(), b"do not overwrite")

    def test_partial_event_count_cannot_be_published(self):
        attempt = self.staging(0)
        receipt = json.loads((attempt / "receipt.json").read_text())
        receipt["processed_events"] = 11
        (attempt / "receipt.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            status.publish_result(self.campaign, 0, attempt)
        self.assertFalse(self.campaign.result_dir(0).exists())

    def test_incomplete_campaign_writes_retry_ids_but_not_merge_list(self):
        status.publish_result(self.campaign, 1, self.staging(1))
        retry, outputs = self.root / "retry.txt", self.root / "outputs.txt"
        self.assertEqual(self.cli("--retry-list", str(retry), "--outputs", str(outputs)), 1)
        self.assertEqual(retry.read_text(), "0\n")
        self.assertFalse(outputs.exists())

    def test_complete_merge_list_has_one_path_per_input_in_order(self):
        for index in (1, 0):
            status.publish_result(self.campaign, index, self.staging(index))
        self.staging(0)  # An abandoned attempt must never enter the merge list.
        outputs = self.root / "outputs.txt"
        self.assertEqual(self.cli("--outputs", str(outputs)), 0)
        self.assertEqual(outputs.read_text().splitlines(),
                         [str(self.campaign.result_dir(i) / "result.root") for i in range(2)])
        with self.assertRaises(FileExistsError):
            self.cli("--outputs", str(outputs))

    def test_duplicate_inputs_and_moving_release_rejected(self):
        self.manifest["files"].append(self.manifest["files"][0])
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            status.load_campaign(self.root)
        self.manifest["files"].pop()
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        self.config["release"] = "AnalysisBase,latest"
        (self.root / "analysis-config.json").write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, "exact"):
            status.load_campaign(self.root)

    def fake_root(self):
        root = Mock()
        source = root.TFile.Open.return_value
        source.IsZombie.return_value = False
        source.GetSize.return_value = 123
        tree = source.Get.return_value
        tree.InheritsFrom.return_value = True
        tree.GetEntries.return_value = 12
        frame = Mock()
        frame.GetColumnNames.return_value = [self.config["branch"]]
        frame.Count.return_value.GetValue.return_value = 12

        def construct_frame(tree_name, url):
            # No RDF graph borrows the metadata TTree after its TFile closes.
            source.Close.assert_called_once()
            return frame

        root.RDataFrame.side_effect = construct_frame
        return root, source, frame

    def run_failed_analysis(self, root, message):
        arguments = ["analyse-file.py", "--campaign", str(self.root), "--index", "0", "--cpus", "2"]
        with patch.dict(sys.modules, {"ROOT": root}), patch.object(sys, "argv", arguments):
            with self.assertRaisesRegex(RuntimeError, message):
                analysis.main()
        self.assertEqual(list((self.root / "results").iterdir()), [])

    def test_source_size_failure_publishes_nothing(self):
        root, source, frame = self.fake_root()
        source.GetSize.return_value = 122
        self.run_failed_analysis(root, "Input size differs")
        source.Close.assert_called_once()
        root.RDataFrame.assert_not_called()

    def test_event_read_failure_publishes_nothing(self):
        root, source, frame = self.fake_root()
        frame.Histo1D.return_value.GetValue.side_effect = RuntimeError("XRootD read failure")
        self.run_failed_analysis(root, "XRootD read failure")
        root.DisableImplicitMT.assert_called_once()
        root.EnableImplicitMT.assert_called_once_with(2)
        root.TFile.Open.assert_called_once()  # No output file was created.

    def test_incomplete_root_event_loop_publishes_nothing(self):
        root, source, frame = self.fake_root()
        frame.Count.return_value.GetValue.return_value = 11
        self.run_failed_analysis(root, "Processed 11 of 12")
        root.TFile.Open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
