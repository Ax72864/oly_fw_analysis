"""OM-3 discovery tests against FakeOm3Camera; no camera network I/O."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from om3_wifi.__main__ import main
from om3_wifi.client import Camera
from om3_wifi.fake import FakeOm3Camera
from penf_wifi.protocol import ClientError


class Om3ClientTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeOm3Camera()
        self.camera = Camera(self.fake)

    def test_identify_accepts_om3(self):
        info = self.camera.identify()
        self.assertEqual(info["model"], "OM-3")
        self.assertEqual([e for e, _ in self.fake.calls], ["get_caminfo.cgi"])

    def test_discover_lists_backup_names_without_writing(self):
        result = self.camera.discover()
        self.assertEqual(result["camera"]["model"], "OM-3")
        self.assertIn("exec_takesettingbackup", result["advertised_commands"])
        self.assertTrue(any("settings-backup" in note for note in result["notes"]))
        self.assertEqual(
            [e for e, _ in self.fake.calls],
            ["get_caminfo.cgi", "get_connectmode.cgi", "get_commandlist.cgi"],
        )

    def test_wrong_model_stops_before_command_list(self):
        self.fake.model = "PEN-F"
        with self.assertRaisesRegex(ClientError, "OM-3 only"):
            self.camera.discover()
        self.assertEqual(len(self.fake.calls), 1)

    def test_writes_are_refused(self):
        for method in (
            lambda: self.camera.session("rec"),
            lambda: self.camera.snapshot(1),
            lambda: self.camera.apply([], None),
        ):
            with self.subTest(method=method), self.assertRaisesRegex(ClientError, "not supported"):
                method()
        self.assertFalse(any(e.startswith("set_") for e, _ in self.fake.calls))

    def test_cli_discover_offline_via_fake(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with patch("om3_wifi.__main__.HTTPTransport", return_value=self.fake):
            code = main(["--out", temp.name, "discover"])
        self.assertEqual(code, 0)
        runs = list(Path(temp.name).glob("*/result.json")) + list(Path(temp.name).iterdir())
        self.assertTrue(runs)


if __name__ == "__main__":
    unittest.main()
