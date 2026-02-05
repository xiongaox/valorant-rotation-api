import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import build_map_pool


class TestBuildScript(unittest.TestCase):
    def test_run_updates_outputs_and_current_pool(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            dist = root / "dist"
            history = root / "history.json"
            config.mkdir()
            (config / "map-name-map.json").write_text(
                json.dumps({"A": "A", "B": "B"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config / "current_pool.json").write_text(
                json.dumps(["A", "B"], ensure_ascii=False),
                encoding="utf-8",
            )
            env = {
                "RETURNING": "",
                "ADDING": "",
                "ROTATED_OUT": "B",
                "VERSION": "v1.00",
                "VERSION_DATE": "2026-02-04",
            }
            build_map_pool.run(
                config,
                dist,
                env,
                bootstrap=False,
                excel_path=None,
                history_path=history,
            )

            maps = json.loads((dist / "maps.json").read_text(encoding="utf-8"))
            meta = json.loads((dist / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual([m["name_zh"] for m in maps["maps"]], ["A", "B"])
            status = {m["name_zh"]: m["status"] for m in maps["maps"]}
            self.assertEqual(status["A"], "in_pool")
            self.assertEqual(status["B"], "rotated_out")
            self.assertEqual(meta["current_pool"], ["A"])
            current = json.loads((config / "current_pool.json").read_text(encoding="utf-8"))
            self.assertEqual(current, ["A"])

    def test_run_raises_on_warnings(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            dist = root / "dist"
            history = root / "history.json"
            config.mkdir()
            (config / "map-name-map.json").write_text(
                json.dumps({"A": "A", "B": "B"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config / "current_pool.json").write_text(
                json.dumps(["A"], ensure_ascii=False),
                encoding="utf-8",
            )
            env = {
                "RETURNING": "A",
                "ADDING": "",
                "ROTATED_OUT": "B",
                "VERSION": "v1.00",
                "VERSION_DATE": "2026-02-04",
            }
            with self.assertRaises(ValueError):
                build_map_pool.run(
                    config,
                    dist,
                    env,
                    bootstrap=False,
                    excel_path=None,
                    history_path=history,
                )

    def test_run_raises_on_missing_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            dist = root / "dist"
            history = root / "history.json"
            config.mkdir()
            (config / "map-name-map.json").write_text(
                json.dumps({"A": "A"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config / "current_pool.json").write_text(
                json.dumps(["A"], ensure_ascii=False),
                encoding="utf-8",
            )
            env = {"RETURNING": "", "ADDING": "", "ROTATED_OUT": ""}
            with self.assertRaises(ValueError):
                build_map_pool.run(
                    config,
                    dist,
                    env,
                    bootstrap=False,
                    excel_path=None,
                    history_path=history,
                )

    def test_run_writes_version_and_date_in_meta(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            dist = root / "dist"
            history = root / "history.json"
            config.mkdir()
            (config / "map-name-map.json").write_text(
                json.dumps({"A": "A"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config / "current_pool.json").write_text(
                json.dumps(["A"], ensure_ascii=False),
                encoding="utf-8",
            )
            env = {
                "RETURNING": "",
                "ADDING": "",
                "ROTATED_OUT": "",
                "VERSION": "v1.00",
                "VERSION_DATE": "2024/4/24",
            }
            build_map_pool.run(
                config,
                dist,
                env,
                bootstrap=False,
                excel_path=None,
                history_path=history,
            )
            meta = json.loads((dist / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["version"], "v1.00")
            self.assertEqual(meta["version_date"], "2024-04-24")

    def test_run_updates_history_overwrite_by_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            dist = root / "dist"
            history = root / "history.json"
            config.mkdir()
            (config / "map-name-map.json").write_text(
                json.dumps({"A": "A"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config / "current_pool.json").write_text(
                json.dumps(["A"], ensure_ascii=False),
                encoding="utf-8",
            )
            history.write_text(
                json.dumps(
                    [
                        {
                            "version": "v1.00",
                            "version_date": "2026-02-01",
                            "current_pool": ["B"],
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            env = {
                "RETURNING": "",
                "ADDING": "",
                "ROTATED_OUT": "",
                "VERSION": "v1.00",
                "VERSION_DATE": "2026-02-04",
            }
            build_map_pool.run(
                config,
                dist,
                env,
                bootstrap=False,
                excel_path=None,
                history_path=history,
            )
            updated = json.loads(history.read_text(encoding="utf-8"))
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0]["version"], "v1.00")
            self.assertEqual(updated[0]["version_date"], "2026-02-04")
            self.assertEqual(updated[0]["current_pool"], ["A"])


class TestCli(unittest.TestCase):
    def test_cli_logs_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            dist = root / "dist"
            config.mkdir()
            (config / "map-name-map.json").write_text(
                json.dumps({"A": "A", "B": "B"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config / "current_pool.json").write_text(
                json.dumps(["A"], ensure_ascii=False),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "RETURNING": "A",
                    "ADDING": "",
                    "ROTATED_OUT": "B",
                    "VERSION": "v1.00",
                    "VERSION_DATE": "2026-02-04",
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_map_pool.py",
                    "--config-dir",
                    str(config),
                    "--dist-dir",
                    str(dist),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ERROR:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


class TestConfigFiles(unittest.TestCase):
    def test_config_files_exist(self):
        self.assertTrue(Path("config/map-name-map.json").exists())
        self.assertTrue(Path("config/current_pool.json").exists())


class TestReadme(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue(Path("README.md").exists())


if __name__ == "__main__":
    unittest.main()
