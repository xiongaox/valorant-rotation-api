import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts import map_pool
except ModuleNotFoundError:
    import map_pool


def run(config_dir, dist_dir, env, bootstrap, excel_path, history_path="history/versions.json"):
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
    version = env.get("VERSION", "").strip()
    version_date_raw = env.get("VERSION_DATE", "").strip()

    map_pool.validate_inputs(returning, adding, rotated_out, map_map)

    current_pool = map_pool.compute_current_pool(base_pool, returning, adding, rotated_out)
    map_pool.validate_pool_size(current_pool)
    map_pool.validate_rotated_out_not_in_pool(current_pool, rotated_out)

    warnings = map_pool.build_warnings(base_pool, returning, adding, rotated_out)
    if warnings:
        raise ValueError(f"warnings present: {warnings}")
    if not version or not version_date_raw:
        raise ValueError("missing VERSION or VERSION_DATE")
    version_date = map_pool.normalize_version_date(version_date_raw)
    maps_payload = {
        "maps": map_pool.build_maps(current_pool, returning, adding, rotated_out, map_map)
    }
    meta_payload = map_pool.build_meta(
        source=source,
        inputs={
            "returning": env.get("RETURNING", ""),
            "adding": env.get("ADDING", ""),
            "rotated_out": env.get("ROTATED_OUT", ""),
        },
        version=version,
        version_date=version_date,
        previous_pool=base_pool,
        current_pool=current_pool,
        rotated_out=rotated_out,
        warnings=warnings,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    map_pool.write_outputs(dist_dir, maps_payload, meta_payload, version=version)
    map_pool.write_current_pool(config_dir / "current_pool.json", current_pool)
    if version:
        entries = map_pool.load_history(history_path)
        entries = map_pool.upsert_history_entry(entries, version, version_date, current_pool)
        map_pool.write_history(history_path, entries)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--dist-dir", default="dist")
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--excel-path", default="地图轮换.xlsx")
    args = parser.parse_args(argv)

    try:
        run(
        config_dir=args.config_dir,
        dist_dir=args.dist_dir,
        env=os.environ,
        bootstrap=args.bootstrap,
        excel_path=args.excel_path,
    )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
