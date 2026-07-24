#!/usr/bin/env python3
"""Collect a quota-conscious, regionally stratified LTC institution detail sample."""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


BASE_URL = "https://apis.data.go.kr/B550928/getLtcInsttDetailInfoService02"
ENDPOINTS = {
    "general": "getGeneralSttusDetailInfoItem02",
    "staff": "getStaffSttusDetailInfoItem02",
    "facility": "getInsttSttusDetailInfoItem02",
    "other": "getInsttEtcDetailInfoItem02",
    "occupancy": "getAceptncNmprDetailInfoItem02",
    "program": "getProgramSttusDetailInfoList02",
}


def select_sample(rows: list[dict[str, str]], per_region: int) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["siDoCd"]][row["adminPttnCd"]].append(row)

    selected: list[dict[str, str]] = []
    for region in sorted(grouped):
        buckets = grouped[region]
        for bucket in buckets.values():
            bucket.sort(key=lambda x: (x["longTermAdminSym"], x.get("adminNm", "")))
        kinds = sorted(buckets)
        positions = {kind: 0 for kind in kinds}
        region_rows: list[dict[str, str]] = []
        while len(region_rows) < per_region:
            added = False
            for kind in kinds:
                pos = positions[kind]
                if pos < len(buckets[kind]):
                    region_rows.append(buckets[kind][pos])
                    positions[kind] += 1
                    added = True
                    if len(region_rows) >= per_region:
                        break
            if not added:
                break
        selected.extend(region_rows)
    return selected


def flatten_item(item: ET.Element | None) -> dict[str, str]:
    if item is None:
        return {}
    return {child.tag: (child.text or "").strip() for child in item}


def fetch_one(endpoint: str, row: dict[str, str], key: str, retries: int) -> dict[str, str]:
    params = urllib.parse.urlencode(
        {
            "serviceKey": key,
            "longTermAdminSym": row["longTermAdminSym"],
            "adminPttnCd": row["adminPttnCd"],
        }
    )
    url = f"{BASE_URL}/{endpoint}?{params}"
    last_error = ""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                body = response.read()
            root = ET.fromstring(body)
            result_code = root.findtext(".//resultCode", default="")
            result_msg = root.findtext(".//resultMsg", default="")
            item = root.find(".//item")
            result = {
                "longTermAdminSym_request": row["longTermAdminSym"],
                "adminPttnCd_request": row["adminPttnCd"],
                "siDoCd_request": row.get("siDoCd", ""),
                "siGunGuCd_request": row.get("siGunGuCd", ""),
                "adminNm_request": row.get("adminNm", ""),
                "resultCode": result_code,
                "resultMsg": result_msg,
            }
            result.update(flatten_item(item))
            return result
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    return {
        "longTermAdminSym_request": row["longTermAdminSym"],
        "adminPttnCd_request": row["adminPttnCd"],
        "siDoCd_request": row.get("siDoCd", ""),
        "siGunGuCd_request": row.get("siGunGuCd", ""),
        "adminNm_request": row.get("adminNm", ""),
        "resultCode": "REQUEST_ERROR",
        "resultMsg": last_error,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    preferred = [
        "longTermAdminSym_request", "adminPttnCd_request", "siDoCd_request",
        "siGunGuCd_request", "adminNm_request", "resultCode", "resultMsg",
    ]
    extra = sorted({key for row in rows for key in row} - set(preferred))
    fields = preferred + extra
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--processed-dir", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--per-region", type=int, default=100)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--endpoints",
        default=",".join(ENDPOINTS),
        help="Comma-separated endpoint aliases to collect",
    )
    args = parser.parse_args()

    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY is required")

    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    sample = select_sample(source_rows, args.per_region)
    args.processed_dir.mkdir(parents=True, exist_ok=True)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.processed_dir / "ltci_detail_sample_index.csv", sample)

    endpoint_names = [name.strip() for name in args.endpoints.split(",") if name.strip()]
    unknown = sorted(set(endpoint_names) - set(ENDPOINTS))
    if unknown:
        raise SystemExit(f"Unknown endpoint aliases: {', '.join(unknown)}")
    chosen_endpoints = {name: ENDPOINTS[name] for name in endpoint_names}
    output: dict[str, list[dict[str, str]]] = {name: [] for name in chosen_endpoints}
    jobs = [(name, endpoint, row) for row in sample for name, endpoint in chosen_endpoints.items()]
    print(f"Selected {len(sample)} services across {len(set(r['siDoCd'] for r in sample))} regions; {len(jobs)} calls")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {
            pool.submit(fetch_one, endpoint, row, key, args.retries): name
            for name, endpoint, row in jobs
        }
        for count, future in enumerate(as_completed(future_map), start=1):
            output[future_map[future]].append(future.result())
            if count % 250 == 0 or count == len(jobs):
                print(f"Completed {count}/{len(jobs)}", flush=True)

    for name, rows in output.items():
        rows.sort(key=lambda x: (x["siDoCd_request"], x["adminPttnCd_request"], x["longTermAdminSym_request"]))
        write_csv(args.processed_dir / f"ltci_detail_{name}_sample.csv", rows)
        with (args.raw_dir / f"ltci_detail_{name}_sample.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "source_rows": len(source_rows),
        "sample_rows": len(sample),
        "regions": sorted(set(r["siDoCd"] for r in sample)),
        "per_region_limit": args.per_region,
        "requested_calls": len(jobs),
        "endpoints": chosen_endpoints,
        "success_counts": {name: sum(r.get("resultCode") == "00" for r in rows) for name, rows in output.items()},
        "error_counts": {name: sum(r.get("resultCode") != "00" for r in rows) for name, rows in output.items()},
    }
    (args.processed_dir / "collection_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
