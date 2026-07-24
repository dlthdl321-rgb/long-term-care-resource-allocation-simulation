"""Collect research-relevant HIRA details for all nursing hospitals."""

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

BASE = "https://apis.data.go.kr/B551182/MadmDtlInfoService2.8"
SOURCE = PROCESSED_DIR / "hira_nursing_hospitals_20260723.csv"
RAW = RAW_DIR / "hira_nursing_hospital_details_20260723"
PROCESSED = PROCESSED_DIR / "hira_nursing_hospital_details_20260723"
ENDPOINTS = {
    "facility": "getEqpInfo2.8",
    "detail": "getDtlInfo2.8",
    "departments": "getDgsbjtInfo2.8",
    "specialists": "getSpcSbjtSdrInfo2.8",
    "nursing_grade": "getNursigGrdInfo2.8",
    "other_staff": "getEtcHstInfo2.8",
    "special_care": "getSpclDiagInfo2.8",
}


def checksum(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fetch(alias: str, endpoint: str, ykiho: str, key: str) -> dict[str, object]:
    path = RAW / alias / f"{hashlib.sha256(ykiho.encode()).hexdigest()}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: bytes | None = path.read_bytes() if path.exists() else None
    error = ""
    if payload is None:
        query = urllib.parse.urlencode({"serviceKey": key, "ykiho": ykiho})
        request = urllib.request.Request(
            f"{BASE}/{endpoint}?{query}", headers={"User-Agent": "ltc-research/1.0"}
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = response.read()
                break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                time.sleep(attempt + 1)
        if payload is not None:
            path.write_bytes(payload)

    result: dict[str, object] = {
        "alias": alias,
        "ykiho": ykiho,
        "resultCode": "REQUEST_ERROR",
        "resultMsg": error,
        "items": [],
        "raw_file": path.as_posix() if payload is not None else "",
        "raw_sha256": checksum(path) if payload is not None else "",
    }
    if payload is None:
        return result
    try:
        root = ET.fromstring(payload)
        result["resultCode"] = root.findtext(".//resultCode", default="")
        result["resultMsg"] = root.findtext(".//resultMsg", default="")
        result["items"] = [
            {child.tag: (child.text or "").strip() for child in item}
            for item in root.findall(".//item")
        ]
    except ET.ParseError as exc:
        result["resultCode"] = "PARSE_ERROR"
        result["resultMsg"] = str(exc)
    return result


def main() -> None:
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY is required.")
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        hospitals = list(csv.DictReader(handle))
    ykihos = sorted({row["ykiho"] for row in hospitals})

    jobs = [(alias, endpoint, ykiho) for alias, endpoint in ENDPOINTS.items() for ykiho in ykihos]
    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = [pool.submit(fetch, alias, endpoint, ykiho, key) for alias, endpoint, ykiho in jobs]
        for count, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if count % 500 == 0 or count == len(futures):
                print(f"Completed {count}/{len(futures)}", flush=True)

    summary: dict[str, object] = {
        "hospitals": len(ykihos),
        "endpoints": ENDPOINTS,
        "requested_calls": len(jobs),
        "credential_persisted": False,
        "endpoint_results": {},
    }
    for alias in ENDPOINTS:
        subset = [row for row in results if row["alias"] == alias]
        output = PROCESSED / f"hira_nursing_hospital_{alias}_20260723.jsonl"
        with output.open("w", encoding="utf-8") as handle:
            for row in sorted(subset, key=lambda value: str(value["ykiho"])):
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        summary["endpoint_results"][alias] = {
            "responses": len(subset),
            "success": sum(row["resultCode"] == "00" for row in subset),
            "errors": sum(row["resultCode"] != "00" for row in subset),
            "items": sum(len(row["items"]) for row in subset),
            "processed_file": output.as_posix(),
        }
    (RAW / "manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
