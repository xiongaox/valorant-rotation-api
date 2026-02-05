# 瓦罗兰特竞技模式图池 API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个可在 GitHub Actions 上定时生成并发布的静态图池 JSON API，支持通过变量（回归/新增/轮出）更新图池。

**Architecture:** Python 脚本从配置与变量生成 `dist/maps.json` 与 `dist/meta.json`。基准图池从 `config/current_pool.json` 滚动更新，首次可从 `地图轮换.xlsx` 读取。GitHub Actions 每日运行并发布到 GitHub Pages。

**Tech Stack:** Python 3 (stdlib), GitHub Actions, GitHub Pages, JSON.

---

### Task 1: 解析输入列表（分隔符/去重）

**Files:**
- Create: `scripts/map_pool.py`
- Create: `tests/test_map_pool.py`

**Step 1: Write the failing test**
```python
# tests/test_map_pool.py
import unittest

from scripts import map_pool

class TestParseList(unittest.TestCase):
    def test_parse_list_basic(self):
        raw = "A、B, C\nD，E；F"
        got = map_pool.parse_list(raw)
        self.assertEqual(got, ["A", "B", "C", "D", "E", "F"])

    def test_normalize_list_dedupe_order(self):
        items = ["A", "B", "A", "C", "B"]
        got = map_pool.normalize_list(items)
        self.assertEqual(got, ["A", "B", "C"])
```

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests.test_map_pool.TestParseList.test_parse_list_basic -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError`

**Step 3: Write minimal implementation**
```python
# scripts/map_pool.py
import re

_SEP_PATTERN = re.compile(r"[、,，;；\n\r\t]+")


def parse_list(raw):
    if not raw:
        return []
    parts = _SEP_PATTERN.split(raw)
    return [p.strip() for p in parts if p and p.strip()]


def normalize_list(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
```

**Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests.test_map_pool.TestParseList -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/map_pool.py tests/test_map_pool.py
git commit -m "feat: add list parsing utilities"
```

---

### Task 2: 校验输入与计算图池

**Files:**
- Modify: `scripts/map_pool.py`
- Modify: `tests/test_map_pool.py`

**Step 1: Write the failing tests**
```python
# tests/test_map_pool.py
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
        map_map = {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F", "G": "G", "H": "H"}
        base = ["A", "B", "C", "D", "E", "F", "G"]
        returning = ["H"]
        adding = []
        rotated = []
        with self.assertRaises(ValueError):
            map_pool.validate_pool_size(
                map_pool.compute_current_pool(base, returning, adding, rotated)
            )
```

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests.test_map_pool.TestValidationAndCompute -v`
Expected: FAIL with `AttributeError` for missing functions

**Step 3: Write minimal implementation**
```python
# scripts/map_pool.py

def validate_inputs(returning, adding, rotated_out, map_map):
    all_lists = [returning, adding, rotated_out]
    # conflict detection
    for i, a in enumerate(all_lists):
        for b in all_lists[i + 1:]:
            overlap = set(a) & set(b)
            if overlap:
                raise ValueError(f"conflicting maps: {sorted(overlap)}")
    # missing map check
    all_items = set(returning + adding + rotated_out)
    missing = [m for m in all_items if m not in map_map]
    if missing:
        raise ValueError(f"unknown maps: {sorted(missing)}")


def compute_current_pool(base_pool, returning, adding, rotated_out):
    base_filtered = [m for m in base_pool if m not in set(rotated_out)]
    # preserve order: base_filtered first, then returning, then adding
    return normalize_list(base_filtered + returning + adding)


def validate_pool_size(current_pool, max_size=7):
    if not current_pool:
        raise ValueError("current pool is empty")
    if len(current_pool) > max_size:
        raise ValueError(f"current pool too large: {len(current_pool)} > {max_size}")
```

**Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests.test_map_pool.TestValidationAndCompute -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/map_pool.py tests/test_map_pool.py
git commit -m "feat: add validation and pool computation"
```

---

### Task 3: 生成地图状态与元数据

**Files:**
- Modify: `scripts/map_pool.py`
- Modify: `tests/test_map_pool.py`

**Step 1: Write the failing tests**
```python
# tests/test_map_pool.py
class TestBuildOutputs(unittest.TestCase):
    def test_build_maps_status(self):
        map_map = {"A": "A", "B": "B", "C": "C"}
        current = ["A", "B", "C"]
        returning = ["B"]
        adding = ["C"]
        got = map_pool.build_maps(current, returning, adding, map_map)
        status = {m["name_zh"]: m["status"] for m in got}
        self.assertEqual(status["A"], "in_pool")
        self.assertEqual(status["B"], "returning")
        self.assertEqual(status["C"], "add")

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
```

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests.test_map_pool.TestBuildOutputs -v`
Expected: FAIL with `AttributeError` for missing functions

**Step 3: Write minimal implementation**
```python
# scripts/map_pool.py

def build_maps(current_pool, returning, adding, map_map):
    returning_set = set(returning)
    adding_set = set(adding)
    out = []
    for name_zh in current_pool:
        if name_zh in returning_set:
            status = "returning"
        elif name_zh in adding_set:
            status = "add"
        else:
            status = "in_pool"
        out.append({
            "name_zh": name_zh,
            "name_en": map_map[name_zh],
            "status": status,
        })
    return out


def build_meta(source, inputs, previous_pool, current_pool, rotated_out, warnings, generated_at):
    return {
        "source": source,
        "generated_at": generated_at,
        "inputs": inputs,
        "previous_pool": previous_pool,
        "current_pool": current_pool,
        "rotated_out": rotated_out,
        "warnings": warnings,
    }
```

**Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests.test_map_pool.TestBuildOutputs -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/map_pool.py tests/test_map_pool.py
git commit -m "feat: add map status and meta builders"
```

---

### Task 4: 配置读取与输出写入

**Files:**
- Modify: `scripts/map_pool.py`
- Modify: `tests/test_map_pool.py`

**Step 1: Write the failing tests**
```python
# tests/test_map_pool.py
import json
import tempfile
from pathlib import Path

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
            map_pool.write_outputs(p, {"maps": []}, {"meta": True})
            self.assertTrue((p / "maps.json").exists())
            self.assertTrue((p / "meta.json").exists())
```

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests.test_map_pool.TestIO -v`
Expected: FAIL with `AttributeError` for missing functions

**Step 3: Write minimal implementation**
```python
# scripts/map_pool.py
import json
from pathlib import Path


def load_map_name_map(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_current_pool(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_current_pool(path, pool):
    Path(path).write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")


def write_outputs(dist_dir, maps_payload, meta_payload):
    dist = Path(dist_dir)
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "maps.json").write_text(
        json.dumps(maps_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (dist / "meta.json").write_text(
        json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

**Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests.test_map_pool.TestIO -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/map_pool.py tests/test_map_pool.py
git commit -m "feat: add config IO and output writer"
```

---

### Task 5: 读取 Excel 基线（仅首次）

**Files:**
- Modify: `scripts/map_pool.py`
- Modify: `tests/test_map_pool.py`

**Step 1: Write the failing test**
```python
# tests/test_map_pool.py
class TestExcelBootstrap(unittest.TestCase):
    def test_read_pool_from_excel(self):
        got = map_pool.read_current_pool_from_excel("地图轮换.xlsx")
        self.assertEqual(
            got,
            ["盐海矿镇", "源工重镇", "微风岛屿", "隐世修所", "幽邃地窟", "深海明珠", "霓虹町"],
        )
```

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests.test_map_pool.TestExcelBootstrap -v`
Expected: FAIL with `AttributeError` for missing function

**Step 3: Write minimal implementation**
```python
# scripts/map_pool.py
import zipfile
import xml.etree.ElementTree as ET


def read_current_pool_from_excel(path):
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        shared_strings = []
        try:
            ss_xml = z.read("xl/sharedStrings.xml")
            ss_root = ET.fromstring(ss_xml)
            for si in ss_root.findall("main:si", ns):
                texts = []
                for t in si.findall(".//main:t", ns):
                    if t.text:
                        texts.append(t.text)
                shared_strings.append("".join(texts))
        except KeyError:
            pass

        wb_xml = z.read("xl/workbook.xml")
        wb_root = ET.fromstring(wb_xml)
        sheets = []
        for sheet in wb_root.findall("main:sheets/main:sheet", ns):
            name = sheet.attrib.get("name")
            rid = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            sheets.append((name, rid))

        rels_xml = z.read("xl/_rels/workbook.xml.rels")
        rels_root = ET.fromstring(rels_xml)
        rels = {}
        for rel in rels_root.findall(
            "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
        ):
            rels[rel.attrib["Id"]] = rel.attrib["Target"]

        # assume first sheet
        _, rid = sheets[0]
        target = rels[rid]
        sheet_path = "xl/" + target.lstrip("/")
        root = ET.fromstring(z.read(sheet_path))

        def cell_value(c):
            v = c.find("main:v", ns)
            if v is None or v.text is None:
                return None
            if c.attrib.get("t") == "s":
                return shared_strings[int(v.text)]
            return v.text

        # find last non-empty row with current pool in last column
        rows = []
        for row in root.findall("main:sheetData/main:row", ns):
            cells = [cell_value(c) for c in row.findall("main:c", ns)]
            if any(cells):
                rows.append(cells)
        if len(rows) < 2:
            raise ValueError("no data rows in excel")
        last = rows[-1]
        current_pool_raw = last[-1]
        if not current_pool_raw:
            raise ValueError("missing current pool in last row")
        return parse_list(current_pool_raw)
```

**Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests.test_map_pool.TestExcelBootstrap -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/map_pool.py tests/test_map_pool.py
git commit -m "feat: add excel bootstrap parser"
```

---

### Task 6: 构建脚本入口与滚动基线更新

**Files:**
- Create: `scripts/build_map_pool.py`
- Create: `tests/test_build_map_pool.py`

**Step 1: Write the failing test**
```python
# tests/test_build_map_pool.py
import json
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
            config.mkdir()
            (config / "map-name-map.json").write_text(
                json.dumps({"A": "A", "B": "B"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config / "current_pool.json").write_text(
                json.dumps(["A", "B"], ensure_ascii=False),
                encoding="utf-8",
            )
            env = {"RETURNING": "", "ADDING": "", "ROTATED_OUT": "B"}
            build_map_pool.run(config, dist, env, bootstrap=False, excel_path=None)

            maps = json.loads((dist / "maps.json").read_text(encoding="utf-8"))
            meta = json.loads((dist / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual([m["name_zh"] for m in maps["maps"]], ["A"])
            self.assertEqual(meta["current_pool"], ["A"])
            # current_pool.json should be updated
            current = json.loads((config / "current_pool.json").read_text(encoding="utf-8"))
            self.assertEqual(current, ["A"])
```

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests.test_build_map_pool.TestBuildScript -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError`

**Step 3: Write minimal implementation**
```python
# scripts/build_map_pool.py
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from scripts import map_pool


def run(config_dir, dist_dir, env, bootstrap, excel_path):
    config_dir = Path(config_dir)
    dist_dir = Path(dist_dir)

    map_map = map_pool.load_map_name_map(config_dir / "map-name-map.json")

    if bootstrap:
        if not excel_path:
            raise ValueError("bootstrap requires excel_path")
        base_pool = map_pool.read_current_pool_from_excel(excel_path)
        map_pool.write_current_pool(config_dir / "current_pool.json", base_pool)
        source = "bootstrap"
    else:
        base_pool = map_pool.load_current_pool(config_dir / "current_pool.json")
        source = "rolling"

    returning = map_pool.normalize_list(map_pool.parse_list(env.get("RETURNING", "")))
    adding = map_pool.normalize_list(map_pool.parse_list(env.get("ADDING", "")))
    rotated_out = map_pool.normalize_list(map_pool.parse_list(env.get("ROTATED_OUT", "")))

    map_pool.validate_inputs(returning, adding, rotated_out, map_map)

    current_pool = map_pool.compute_current_pool(base_pool, returning, adding, rotated_out)
    map_pool.validate_pool_size(current_pool)

    maps_payload = {"maps": map_pool.build_maps(current_pool, returning, adding, map_map)}
    meta_payload = map_pool.build_meta(
        source=source,
        inputs={
            "returning": env.get("RETURNING", ""),
            "adding": env.get("ADDING", ""),
            "rotated_out": env.get("ROTATED_OUT", ""),
        },
        previous_pool=base_pool,
        current_pool=current_pool,
        rotated_out=rotated_out,
        warnings=[],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    map_pool.write_outputs(dist_dir, maps_payload, meta_payload)
    # rolling update
    map_pool.write_current_pool(config_dir / "current_pool.json", current_pool)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--dist-dir", default="dist")
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--excel-path", default="地图轮换.xlsx")
    args = parser.parse_args(argv)

    run(
        config_dir=args.config_dir,
        dist_dir=args.dist_dir,
        env=os.environ,
        bootstrap=args.bootstrap,
        excel_path=args.excel_path,
    )


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests.test_build_map_pool.TestBuildScript -v`
Expected: PASS

**Step 5: Commit**
```bash
git add scripts/build_map_pool.py tests/test_build_map_pool.py
git commit -m "feat: add build script entrypoint"
```

---

### Task 7: 添加配置文件与 GitHub Actions 工作流

**Files:**
- Create: `config/map-name-map.json`
- Create: `config/current_pool.json`
- Create: `.github/workflows/build-map-pool.yml`

**Step 1: Write the failing test**
```python
# tests/test_build_map_pool.py
class TestConfigFiles(unittest.TestCase):
    def test_config_files_exist(self):
        self.assertTrue(Path("config/map-name-map.json").exists())
        self.assertTrue(Path("config/current_pool.json").exists())
```

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests.test_build_map_pool.TestConfigFiles -v`
Expected: FAIL with missing files

**Step 3: Write minimal implementation**
```json
// config/map-name-map.json
{
  "亚海悬城": "Ascent",
  "幽邃地窟": "Abyss",
  "霓虹町": "Split",
  "裂变峡谷": "Fracture",
  "源工重镇": "Bind",
  "微风岛屿": "Breeze",
  "莲华古城": "Lotus",
  "日落之城": "Sunset",
  "深海明珠": "Pearl",
  "森寒冬港": "Icebox",
  "盐海矿镇": "Corrode",
  "隐世修所": "Haven"
}
```

```json
// config/current_pool.json
[
  "盐海矿镇",
  "源工重镇",
  "微风岛屿",
  "隐世修所",
  "幽邃地窟",
  "深海明珠",
  "霓虹町"
]
```

```yaml
# .github/workflows/build-map-pool.yml
name: Build Map Pool

on:
  schedule:
    - cron: "0 1 * * *"
  workflow_dispatch: {}

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Build map pool
        env:
          RETURNING: ${{ vars.RETURNING }}
          ADDING: ${{ vars.ADDING }}
          ROTATED_OUT: ${{ vars.ROTATED_OUT }}
        run: |
          python3 scripts/build_map_pool.py
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/deploy-pages@v4
        id: deployment
```

**Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests.test_build_map_pool.TestConfigFiles -v`
Expected: PASS

**Step 5: Commit**
```bash
git add config/map-name-map.json config/current_pool.json .github/workflows/build-map-pool.yml
git commit -m "feat: add config files and CI workflow"
```

---

### Task 8: README 与使用说明（可选）

**Files:**
- Create: `README.md`

**Step 1: Write the failing test**
```python
# tests/test_build_map_pool.py
class TestReadme(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue(Path("README.md").exists())
```

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest tests.test_build_map_pool.TestReadme -v`
Expected: FAIL with missing file

**Step 3: Write minimal implementation**
```markdown
# Valorant Map Pool API

- 修改 GitHub Actions 变量 `RETURNING` / `ADDING` / `ROTATED_OUT` 后，手动触发或等待定时任务。
- 生成结果发布到 GitHub Pages：`/maps.json` 与 `/meta.json`。
```

**Step 4: Run test to verify it passes**
Run: `python3 -m unittest tests.test_build_map_pool.TestReadme -v`
Expected: PASS

**Step 5: Commit**
```bash
git add README.md
git commit -m "docs: add usage readme"
```

---

## Notes
- 若仓库不是 Git，commit 步骤可跳过。
- 若不再保留 `地图轮换.xlsx`，请删除 Task 5 测试或提供 fixtures。
- Cron 时间为 UTC `01:00`，如需调整到北京时间请改为 `17:00` UTC。
