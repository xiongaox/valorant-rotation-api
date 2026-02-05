import json
import re
from datetime import date
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

_SEP_PATTERN = re.compile(r"[、,， ]+")


def parse_list(raw):
    if not raw:
        return []
    if "\n" in raw or "\r" in raw:
        raise ValueError("newline separators are not allowed; use 、，, or space")
    parts = _SEP_PATTERN.split(raw)
    return [p.strip() for p in parts if p and p.strip()]


def normalize_version_date(raw):
    if not raw:
        raise ValueError("VERSION_DATE is required")
    match = re.match(r"^(?P<y>\d{4})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})$", raw.strip())
    if not match:
        raise ValueError("invalid VERSION_DATE format; use YYYY-MM-DD or YYYY/M/D")
    year = int(match.group("y"))
    month = int(match.group("m"))
    day = int(match.group("d"))
    normalized = date(year, month, day)
    return normalized.strftime("%Y-%m-%d")


def normalize_list(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def validate_inputs(returning, adding, rotated_out, map_map):
    all_lists = [returning, adding, rotated_out]
    for i, a in enumerate(all_lists):
        for b in all_lists[i + 1 :]:
            overlap = set(a) & set(b)
            if overlap:
                raise ValueError(f"conflicting maps: {sorted(overlap)}")

    all_items = set(returning + adding + rotated_out)
    missing = [m for m in all_items if m not in map_map]
    if missing:
        raise ValueError(f"unknown maps: {sorted(missing)}")


def compute_current_pool(base_pool, returning, adding, rotated_out):
    base_filtered = [m for m in base_pool if m not in set(rotated_out)]
    return normalize_list(base_filtered + returning + adding)


def validate_pool_size(current_pool, max_size=7):
    if not current_pool:
        raise ValueError("current pool is empty")
    if len(current_pool) > max_size:
        raise ValueError(f"current pool too large: {len(current_pool)} > {max_size}")


def validate_rotated_out_not_in_pool(current_pool, rotated_out):
    overlap = set(current_pool) & set(rotated_out)
    if overlap:
        raise ValueError(f"rotated_out still in current pool: {sorted(overlap)}")


def build_maps(current_pool, returning, adding, rotated_out, map_map):
    returning_set = set(returning)
    adding_set = set(adding)
    current_set = set(current_pool)
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
    for name_zh in rotated_out:
        if name_zh in current_set:
            continue
        out.append({
            "name_zh": name_zh,
            "name_en": map_map[name_zh],
            "status": "rotated_out",
        })
    return out


def build_meta(
    source,
    inputs,
    previous_pool,
    current_pool,
    rotated_out,
    warnings,
    generated_at,
    version="",
    version_date="",
):
    return {
        "source": source,
        "generated_at": generated_at,
        "version": version,
        "version_date": version_date,
        "inputs": inputs,
        "previous_pool": previous_pool,
        "current_pool": current_pool,
        "rotated_out": rotated_out,
        "warnings": warnings,
    }


def build_warnings(base_pool, returning, adding, rotated_out):
    base_set = set(base_pool)
    warnings = []

    rotated_missing = [m for m in rotated_out if m not in base_set]
    if rotated_missing:
        warnings.append({"type": "rotated_out_not_in_pool", "maps": rotated_missing})

    returning_existing = [m for m in returning if m in base_set]
    if returning_existing:
        warnings.append({"type": "returning_already_in_pool", "maps": returning_existing})

    adding_existing = [m for m in adding if m in base_set]
    if adding_existing:
        warnings.append({"type": "adding_already_in_pool", "maps": adding_existing})

    return warnings


def load_map_name_map(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_current_pool(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_current_pool(path, pool):
    Path(path).write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")


def write_outputs(dist_dir, maps_payload, meta_payload, version=""):
    dist = Path(dist_dir)
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "maps.json").write_text(
        json.dumps(maps_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (dist / "meta.json").write_text(
        json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if version:
        version_dir = dist / version
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "maps.json").write_text(
            json.dumps(maps_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (version_dir / "meta.json").write_text(
            json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def load_history(path):
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_history(path, entries):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_history_entry(entries, version, version_date, current_pool):
    updated = []
    replaced = False
    for entry in entries:
        if entry.get("version") == version:
            updated.append(
                {
                    "version": version,
                    "version_date": version_date,
                    "current_pool": current_pool,
                }
            )
            replaced = True
        else:
            updated.append(entry)
    if not replaced:
        updated.append(
            {
                "version": version,
                "version_date": version_date,
                "current_pool": current_pool,
            }
        )
    return updated


def _col_to_index(cell_ref):
    letters = ""
    for ch in cell_ref:
        if ch.isalpha():
            letters += ch.upper()
        else:
            break
    if not letters:
        return None
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


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

        header = {}
        last_value = None
        header_row_seen = False

        for row in root.findall("main:sheetData/main:row", ns):
            cells = row.findall("main:c", ns)
            row_map = {}
            for c in cells:
                ref = c.attrib.get("r", "")
                col_idx = _col_to_index(ref)
                val = cell_value(c)
                if col_idx is not None:
                    row_map[col_idx] = val

            if not row_map:
                continue

            if not header_row_seen:
                for col_idx, val in row_map.items():
                    if val:
                        header[val] = col_idx
                header_row_seen = True
                continue

            current_col = header.get("当前图池")
            if current_col is None:
                raise ValueError("header missing 当前图池")

            current_val = row_map.get(current_col)
            if current_val:
                last_value = current_val

        if not last_value:
            raise ValueError("missing current pool in last row")
        return parse_list(last_value)
