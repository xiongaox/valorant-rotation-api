import json
import tempfile
import unittest
from pathlib import Path

from scripts import map_pool


class TestParseList(unittest.TestCase):
    def test_parse_list_basic(self):
        raw = "A、B, C D，E"
        got = map_pool.parse_list(raw)
        self.assertEqual(got, ["A", "B", "C", "D", "E"])

    def test_parse_list_rejects_newlines(self):
        raw = "A\nB"
        with self.assertRaises(ValueError):
            map_pool.parse_list(raw)

    def test_normalize_list_dedupe_order(self):
        items = ["A", "B", "A", "C", "B"]
        got = map_pool.normalize_list(items)
        self.assertEqual(got, ["A", "B", "C"])


class TestValidationAndCompute(unittest.TestCase):
    def test_validate_conflict(self):
        map_map = {"A": "A"}
        with self.assertRaises(ValueError):
            map_pool.validate_inputs(
                returning=["A"], adding=["A"], rotated_out=[], map_map=map_map
            )

    def test_validate_missing_map(self):
        map_map = {"A": "A"}
        with self.assertRaises(ValueError):
            map_pool.validate_inputs(
                returning=["B"], adding=[], rotated_out=[], map_map=map_map
            )

    def test_compute_current_pool(self):
        base = ["A", "B", "C"]
        returning = ["D"]
        adding = ["E"]
        rotated = ["B"]
        got = map_pool.compute_current_pool(base, returning, adding, rotated)
        self.assertEqual(got, ["A", "C", "D", "E"])

    def test_validate_pool_size(self):
        base = ["A", "B", "C", "D", "E", "F", "G"]
        returning = ["H"]
        adding = []
        rotated = []
        with self.assertRaises(ValueError):
            map_pool.validate_pool_size(
                map_pool.compute_current_pool(base, returning, adding, rotated)
            )

    def test_validate_rotated_out_not_in_pool(self):
        current = ["A", "B"]
        rotated_out = ["B", "C"]
        with self.assertRaises(ValueError):
            map_pool.validate_rotated_out_not_in_pool(current, rotated_out)


class TestWarnings(unittest.TestCase):
    def test_build_warnings(self):
        base = ["A", "B", "C"]
        returning = ["B", "D"]
        adding = ["C"]
        rotated_out = ["X", "A"]
        warnings = map_pool.build_warnings(base, returning, adding, rotated_out)
        self.assertEqual(
            warnings,
            [
                {"type": "rotated_out_not_in_pool", "maps": ["X"]},
                {"type": "returning_already_in_pool", "maps": ["B"]},
                {"type": "adding_already_in_pool", "maps": ["C"]},
            ],
        )


class TestBuildOutputs(unittest.TestCase):
    def test_build_maps_status(self):
        map_map = {"A": "A", "B": "B", "C": "C", "D": "D"}
        current = ["A", "B", "C"]
        returning = ["B"]
        adding = ["C"]
        rotated_out = ["D"]
        got = map_pool.build_maps(current, returning, adding, rotated_out, map_map)
        status = {m["name_zh"]: m["status"] for m in got}
        self.assertEqual(status["A"], "in_pool")
        self.assertEqual(status["B"], "returning")
        self.assertEqual(status["C"], "add")
        self.assertEqual(status["D"], "rotated_out")

    def test_build_meta(self):
        meta = map_pool.build_meta(
            source="rolling",
            inputs={"returning": "B", "adding": "", "rotated_out": "A"},
            previous_pool=["A", "B"],
            current_pool=["B"],
            rotated_out=["A"],
            warnings=[],
            generated_at="2026-02-04T00:00:00Z",
        )
        self.assertEqual(meta["source"], "rolling")
        self.assertEqual(meta["current_pool"], ["B"])


class TestIO(unittest.TestCase):
    def test_load_and_write_current_pool(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            pool_path = p / "current_pool.json"
            map_pool.write_current_pool(pool_path, ["A", "B"])
            got = map_pool.load_current_pool(pool_path)
            self.assertEqual(got, ["A", "B"])

    def test_load_map_name_map(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "map.json"
            p.write_text(json.dumps({"A": "A"}), encoding="utf-8")
            got = map_pool.load_map_name_map(p)
            self.assertEqual(got, {"A": "A"})

    def test_write_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            map_pool.write_outputs(p, {"maps": []}, {"meta": True}, version="v1.00")
            self.assertTrue((p / "maps.json").exists())
            self.assertTrue((p / "meta.json").exists())
            self.assertTrue((p / "v1.00" / "maps.json").exists())
            self.assertTrue((p / "v1.00" / "meta.json").exists())


class TestExcelBootstrap(unittest.TestCase):
    def test_read_pool_from_excel(self):
        got = map_pool.read_current_pool_from_excel("地图轮换.xlsx")
        self.assertEqual(
            got,
            ["盐海矿镇", "源工重镇", "微风岛屿", "隐世修所", "幽邃地窟", "深海明珠", "霓虹町"],
        )


if __name__ == "__main__":
    unittest.main()
