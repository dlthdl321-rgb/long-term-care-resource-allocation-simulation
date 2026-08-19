from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = Path(__file__).resolve().parents[1]
PUBLIC = WEB / "public" / "data"
ANALYSIS = ROOT / "03_데이터" / "data" / "analysis_ready"
RESULTS = ROOT / "03_데이터" / "outputs"
def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_json(name: str, rows: object) -> None:
    path = PUBLIC / f"{name}.json"
    path.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


regions = json.loads((PUBLIC / "regions.json").read_text(encoding="utf-8"))
region_by_name = {
    (row["sido_name"], row["sigungu_name"]): row["region_code"] for row in regions
}

# 직종별 공급: 동일 서비스의 재가노인복지시설·재가장기요양기관 행을 합산한다.
supply_rows = read_csv(ANALYSIS / "ltci_supply_sigungu_service_type_20260610.csv")
service_keywords = {
    "방문요양": "방문요양",
    "방문간호": "방문간호",
    "주야간보호": "주야간보호",
}
workforce_fields = [
    "기관수",
    "정원",
    "사회복지사",
    "간호사",
    "간호조무사",
    "물리치료사",
    "작업치료사",
    "요양보호사",
]
workforce = defaultdict(lambda: defaultdict(float))
for row in supply_rows:
    code = region_by_name.get((row["시도명"], row["시군구명"]))
    if not code:
        continue
    service = next(
        (name for name, keyword in service_keywords.items() if keyword in row["기관유형명"]),
        None,
    )
    if not service:
        continue
    key = (code, service)
    for field in workforce_fields:
        workforce[key][field] += float(row.get(field) or 0)

workforce_output = []
for (code, service), values in sorted(workforce.items()):
    region = next(row for row in regions if row["region_code"] == code)
    item = {
        "region_code": code,
        "sido_name": region["sido_name"],
        "sigungu_name": region["sigungu_name"],
        "service": service,
        "data_reference_date": "2026-06-10",
    }
    item.update({field: str(value) for field, value in values.items()})
    workforce_output.append(item)
write_json("workforce", workforce_output)

# 지역별 관측 추이: 연말 고령인구와 장기요양 인정수요를 결합한다.
history = defaultdict(dict)
population_rows = read_csv(
    ANALYSIS / "elderly_population_sigungu_year_end_2022_2025.csv"
)
for row in population_rows:
    code = region_by_name.get((row["시도명"], row["시군구명"]))
    if not code:
        continue
    year = row["기준일"][:4]
    history[(code, year)].update(
        {
            "region_code": code,
            "year": year,
            "population_total": row["총인구"],
            "population_65_plus": row["65세이상인구"],
            "population_85_plus": row["85세이상인구"],
            "aging_rate": row["고령화율"],
        }
    )
demand_rows = read_csv(ANALYSIS / "ltci_demand_sigungu_year_end_2022_2025.csv")
for row in demand_rows:
    code = region_by_name.get((row["시도"], row["시군구"]))
    if not code:
        continue
    year = row["기준일"][:4]
    history[(code, year)].update(
        {
            "ltci_applicants_public": row["신청자_공개값합계"],
            "ltci_recognized_public": row["인정자_공개값합계"],
            "ltci_recognized_lower": row["인정자_추정하한"],
            "ltci_recognized_upper": row["인정자_추정상한"],
            "suppression_warning": row["비공개규칙주의"],
        }
    )
write_json(
    "history",
    [row for _, row in sorted(history.items()) if row.get("population_total")],
)

# 화면·보고서 공통 기준일과 품질 설명.
quality = [
    {
        "dataset": "지역 인구",
        "reference_date": "2026-06",
        "coverage": "시군구 255곳 및 읍면동 3,618행",
        "status": "사용 가능",
        "warning": "주민등록 인구이며 실제 돌봄이용자 수가 아님",
    },
    {
        "dataset": "장기요양 수요",
        "reference_date": "2026-05",
        "coverage": "시군구 235곳",
        "status": "주의",
        "warning": "비공개 셀이 있어 공개값과 추정 하한·상한을 구분해야 함",
    },
    {
        "dataset": "기관·인력·정원",
        "reference_date": "2026-06-10",
        "coverage": "기관유형×시군구 3,600행",
        "status": "사용 가능",
        "warning": "등록·집계 자원이며 실시간 신규접수 가능 여부를 뜻하지 않음",
    },
    {
        "dataset": "기관 현원·정원",
        "reference_date": "2025-04-01",
        "coverage": "기관유형×시군구 2,945행",
        "status": "주의",
        "warning": "현원 결측이 있는 행은 가동률을 해석하지 않음",
    },
    {
        "dataset": "접근성",
        "reference_date": "시뮬레이션 입력",
        "coverage": "같은 도 기반 기여관계 5,348행",
        "status": "탐색 가정",
        "warning": "실제 인접관계·도로 이동시간·기관 방문권역이 아님",
    },
]
write_json("quality", quality)

# 채용 포트폴리오와 대시보드가 함께 사용하는 검증된 핵심 결과.
# 숫자는 화면에서 다시 입력하지 않고 분석 산출물과 공개 기준선에서 읽는다.
baseline_rows = json.loads((PUBLIC / "baseline.json").read_text(encoding="utf-8"))
representative_rows = read_csv(
    RESULTS / "representative_visit_nursing_allocation" / "scenario_metrics.csv"
)
representative_by_strategy = {row["strategy"]: row for row in representative_rows}
visit_nursing_missing = sum(
    row["service"] == "방문간호"
    and row["resource_type"] == "기관"
    and row["provider_missing"] == "True"
    for row in baseline_rows
)
demand_strategy = representative_by_strategy["demand_proportional"]
missing_strategy = representative_by_strategy["zero_provider_priority"]
portfolio_summary = [{
    "region_count": str(len(regions)),
    "service_count": "3",
    "resource_dimension_count": str(
        len({(row["service"], row["resource_type"]) for row in baseline_rows})
    ),
    "visit_nursing_provider_missing": str(visit_nursing_missing),
    "representative_budget": demand_strategy["resource_budget"],
    "demand_proportional_benefited_demand": demand_strategy["benefited_demand"],
    "zero_provider_gap_reduction": missing_strategy["continuous_gap_reduction"],
    "zero_provider_regions_reduced": missing_strategy["zero_provider_regions_reduced"],
    "generated_from": (
        "public/data/baseline.json;"
        "03_데이터/outputs/representative_visit_nursing_allocation/scenario_metrics.csv"
    ),
}]
write_json("portfolio-summary", portfolio_summary)

print(
    json.dumps(
        {
            "workforce": len(workforce_output),
            "history": len(history),
            "quality": len(quality),
            "portfolio_summary": len(portfolio_summary),
        },
        ensure_ascii=False,
    )
)
