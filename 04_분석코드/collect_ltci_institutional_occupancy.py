"""Collect current occupancy for nationwide institutional LTC services.

The detailed API is institution-by-institution. To stay within the 10,000-call
development quota, this collector targets A03 and A04, the facility services
for which occupancy is meaningful. General, capacity and staffing information
is already available in the nationwide NHIS facility-status source file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from project_paths import PROCESSED_DIR, RAW_DIR

BASE_URL = (
    "https://apis.data.go.kr/B550928/getLtcInsttDetailInfoService02/"
    "getAceptncNmprDetailInfoItem02"
)
SOURCE = PROCESSED_DIR / "ltci_institutions_search_nationwide_20260722.csv"
DETAIL_RAW_DIR = RAW_DIR / "nhis_ltci_detail_occupancy_20260723"
OUTPUT = PROCESSED_DIR / "nhis_ltci_institutional_occupancy_20260723.csv"
MANIFEST = DETAIL_RAW_DIR / "manifest.json"
TARGET_TYPES = {"A03", "A04"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def flatten_item(root: ET.Element) -> dict[str, str]:
    item = root.find(".//item")
    if item is None:
        return {}
    return {child.tag: (child.text or "").strip() for child in item}


def fetch(row: dict[str, str], key: str) -> dict[str, str]:
    institution = row["longTermAdminSym"]
    service_type = row["adminPttnCd"]
    path = DETAIL_RAW_DIR / service_type / f"{institution}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: bytes | None = None
    error = ""

    if path.exists():
        payload = path.read_bytes()
    else:
        query = urllib.parse.urlencode(
            {
                "serviceKey": key,
                "longTermAdminSym": institution,
                "adminPttnCd": service_type,
            }
        )
        request = urllib.request.Request(
            f"{BASE_URL}?{query}", headers={"User-Agent": "ltc-research/1.0"}
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = response.read()
                break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                time.sleep(1.0 + attempt)
        if payload is not None:
            path.write_bytes(payload)

    result = {
        "longTermAdminSym": institution,
        "adminPttnCd": service_type,
        "adminNm": row.get("adminNm", ""),
        "siDoCd": row.get("siDoCd", ""),
        "siGunGuCd": row.get("siGunGuCd", ""),
        "resultCode": "REQUEST_ERROR",
        "resultMsg": error,
        "fmNowPer": "",
        "maNowPer": "",
        "totPer": "",
        "raw_file": path.as_posix() if payload is not None else "",
        "raw_sha256": digest(path) if payload is not None else "",
    }
    if payload is None:
        return result
    try:
        root = ET.fromstring(payload)
        result["resultCode"] = root.findtext(".//resultCode", default="")
        result["resultMsg"] = root.findtext(".//resultMsg", default="")
        result.update(flatten_item(root))
    except ET.ParseError as exc:
        result["resultCode"] = "PARSE_ERROR"
        result["resultMsg"] = str(exc)
    return result


def main() -> None:
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY is required.")
    DETAIL_RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        rows = [
            row for row in csv.DictReader(handle)
            if row.get("adminPttnCd") in TARGET_TYPES
        ]
    unique = {
        (row["longTermAdminSym"], row["adminPttnCd"]): row for row in rows
    }
    targets = [unique[key] for key in sorted(unique)]
    results: list[dict[str, str]] = []
    # Keep concurrency moderate because this public API resets connections
    # when many institution-level requests arrive simultaneously.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(fetch, row, key) for row in targets]
        for count, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if count % 500 == 0 or count == len(futures):
                print(f"Completed {count}/{len(futures)}", flush=True)

    results.sort(key=lambda row: (row["adminPttnCd"], row["longTermAdminSym"]))
    fields = [
        "longTermAdminSym", "adminPttnCd", "adminNm", "siDoCd", "siGunGuCd",
        "resultCode", "resultMsg", "fmNowPer", "maNowPer", "totPer",
        "raw_file", "raw_sha256",
    ]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    success = [row for row in results if row["resultCode"] == "00"]
    summary = {
        "source": str(SOURCE),
        "endpoint": BASE_URL,
        "target_service_types": sorted(TARGET_TYPES),
        "targets": len(targets),
        "success": len(success),
        "errors": len(results) - len(success),
        "nonblank_total_occupancy": sum(row.get("totPer", "") != "" for row in success),
        "zero_total_occupancy": sum(row.get("totPer", "") == "0" for row in success),
        "processed_file": str(OUTPUT),
        "credential_persisted": False,
    }
    MANIFEST.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

