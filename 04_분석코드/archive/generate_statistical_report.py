"""Python 산출물을 이용해 기술·추론통계 Markdown 보고서를 생성한다."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import analyze_ltci_resource_allocation as analysis


ROOT = analysis.PROJECT_ROOT
REPORT_DIR = ROOT.parent / "02_분석보고서"
ANALYSIS_DIR = ROOT / "outputs" / "analysis"
STAT_DIR = ROOT / "outputs" / "statistical_readiness"
CONFIG_PATH = ROOT / "config" / "statistical_config.json"


def format_number(value: object, digits: int = 3) -> str:
    if pd.isna(value):
        return "-"
    number = float(value)
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    return f"{number:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    profiles = pd.read_csv(
        STAT_DIR / "service_statistical_profiles.csv",
        encoding="utf-8-sig",
    )
    inference = pd.read_csv(
        ANALYSIS_DIR / "hypothesis_inference_results.csv",
        encoding="utf-8-sig",
    )
    hypothesis_descriptive = pd.read_csv(
        ANALYSIS_DIR / "hypothesis_descriptive_results.csv",
        encoding="utf-8-sig",
    )
    metrics = pd.read_csv(
        ANALYSIS_DIR / "current_region_service_metrics.csv",
        encoding="utf-8-sig",
        low_memory=False,
    )
    demand_panel = pd.read_csv(
        analysis.FILES["demand_panel"],
        encoding="utf-8-sig",
        low_memory=False,
    )
    demand_panel["기준일"] = pd.to_datetime(
        demand_panel["기준일"], errors="coerce"
    )
    demand_year = (
        demand_panel.groupby(demand_panel["기준일"].dt.year)
        .agg(
            인정자공개합계=("인정자_공개값합계", "sum"),
            인정자추정하한=("인정자_추정하한", "sum"),
            인정자추정상한=("인정자_추정상한", "sum"),
        )
        .reset_index(names="연도")
    )

    selected_codes = ["A03", "A04", "B01", "B02", "B03", "B05", "C01", "C03"]
    selected = profiles.loc[profiles["기관유형코드"].isin(selected_codes)].copy()
    selected["order"] = selected["기관유형코드"].map(
        {code: index for index, code in enumerate(selected_codes)}
    )
    selected = selected.sort_values("order")

    tested = inference.loc[inference["검정"].ne("제외")].copy()
    tested = tested.sort_values("FDR보정p값")
    excluded = inference.loc[inference["검정"].eq("제외")].copy()
    significant = tested.loc[tested["FDR_0.05기각"].astype(str).eq("True")]

    b_summary = hypothesis_descriptive.loc[
        hypothesis_descriptive["기관유형코드"].isin(selected_codes)
    ].copy()
    b_summary["order"] = b_summary["기관유형코드"].map(
        {code: index for index, code in enumerate(selected_codes)}
    )
    b_summary = b_summary.sort_values("order")

    lines = [
        "# 기초 통계 검증 보고서 — 전국 시군구 장기요양 서비스 공급압력",
        "",
        "> **문서 상태:** 이 보고서는 전국 229개 분석지역×39개 기관유형을 사용한 "
        "기존 기초검증 결과다. 최신 연구범위인 도 소속 농촌 군×방문요양·방문간호·"
        "주야간보호의 Q1~Q3 결과가 아니며, 최신 정의는 "
        "[데이터 기반 분석기획](06_데이터기반_분석기획.md)을 기준으로 한다.",
        "",
        "- 작성일: 2026-07-23",
        "- 분석 단위: 시군구×기관유형",
        "- 분석지역: 229개",
        "- 서비스 유형: 39개",
        "- 전처리·통계 실행: Python",
        "- 추론통계 성격: 전국 행정자료를 이용한 탐색적 지역 연관성 분석",
        "",
        "## 1. 분석 목적과 해석 범위",
        "",
        "2022~2025년 장기요양 인정수요 변화와 2026년 지역별 서비스 공급을 "
        "기술통계로 확인하고, 수요 증가율과 현재 인정자 1,000명당 기관 수의 "
        "관계를 서비스별 Spearman 순위상관으로 탐색했다.",
        "",
        "이 자료는 임의표본이 아니라 전국 행정자료에 가까우므로 p값보다 분포, "
        "효과크기, 민감도와 데이터 한계를 우선한다. 분석 결과는 실제 서비스 부족, "
        "미충족수요 또는 인과효과를 의미하지 않는다.",
        "",
        "## 2. 데이터와 전처리 검증",
        "",
        "- 실행 계보: `data/raw` 원본 XLSX·CSV → Python 시트 추출·인코딩·집계 "
        "→ `data/analysis_ready` → Python 기술·추론통계",
        "- 수작업 값 수정: 없음. 원본 파일, 시트, 행 수, SHA-256은 "
        "`outputs/raw_preprocessing/lineage_manifest.json`에 기록",
        "- 핵심 출처: [국민건강보험공단 장기요양 등급판정 현황]"
        "(https://www.data.go.kr/data/3051421/fileData.do), "
        "[국민건강보험공단 장기요양기관 시설별 현황]"
        "(https://www.data.go.kr/data/15124763/fileData.do), "
        "[행정안전부 주민등록 인구]"
        "(https://www.data.go.kr/data/15097972/fileData.do), "
        "[행정안전부 주민등록 1인세대]"
        "(https://www.data.go.kr/data/15099160/fileData.do)",
        "- 지역명 표준화: 시도 축약명, 복합시 일반구, 세종, 군위군 이동, "
        "인천 남구→미추홀구 반영",
        "- 최종 완전격자: 229개 지역×39개 서비스=8,931행",
        "- 지역 결합률: 인구·1인세대·공급 모두 100%",
        "- 지역×서비스 중복: 0건",
        "- 기관·정원·직종별 인력 집계 전후 합계: 전부 일치",
        "- 동일 입력 2회 전처리: 핵심 결과 완전 일치",
        "",
        "## 3. 지표 정의",
        "",
        "| 지표 | 정의 | 주의 |",
        "| --- | --- | --- |",
        "| 인정자 1,000명당 기관 수 | 전처리된 공급자료의 서비스별 기관 수÷인정자 추정값×1,000 | 실제 서비스 유형별 이용수요가 아님 |",
        "| 기관 1곳당 인정자 | 인정자 추정값÷기관 수 | 기관 0 지역에서는 계산하지 않음 |",
        "| 정원 공급률 | 정원÷인정자 추정값×1,000 | 정원 사용가능 서비스에만 적용 |",
        "| 공급 0 지역 | 전수 시설표에서 해당 지역×유형 조합이 관측되지 않음 | 미보고 가능성을 완전히 배제하지 못함 |",
        "| 인정자 증가율 | 2022년과 2025년 인정자 추정 중앙값 비교 | 비공개값 민감도 필요 |",
        "",
        "## 4. 기술통계",
        "",
        "### 4.1 연도별 장기요양 인정수요",
        "",
    ]
    lines.extend(
        markdown_table(
            ["연도", "공개합계", "추정 하한", "추정 상한"],
            [
                [
                    int(row["연도"]),
                    format_number(row["인정자공개합계"], 0),
                    format_number(row["인정자추정하한"], 0),
                    format_number(row["인정자추정상한"], 0),
                ]
                for _, row in demand_year.iterrows()
            ],
        )
    )
    lines.extend(
        [
            "",
            "공개합계 기준 인정자는 2022년 1,019,130명에서 2025년 "
            "1,235,045명으로 증가했다. 최근 자료에는 5명 미만 비공개셀이 있으므로 "
            "지역 분석은 공개합계가 아니라 하한·중앙·상한으로 수행한다.",
            "",
            "### 4.2 주요 서비스의 인정자 1,000명당 기관 수 분포",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            [
                "코드",
                "서비스",
                "평균",
                "중앙값",
                "Q1",
                "Q3",
                "표준편차",
                "공급 0 지역",
            ],
            [
                [
                    row["기관유형코드"],
                    row["기관유형명"],
                    format_number(row["평균"]),
                    format_number(row["중앙값"]),
                    format_number(row["1사분위수"]),
                    format_number(row["3사분위수"]),
                    format_number(row["표준편차"]),
                    int(row["공급0지역수"]),
                ]
                for _, row in selected.iterrows()
            ],
        )
    )
    lines.extend(
        [
            "",
            "평균과 중앙값이 차이나고 IQR 이상치가 존재하므로 평균만으로 지역 "
            "공급 수준을 설명하지 않는다. 상세 분포는 "
            "`outputs/analysis/supply_rate_distributions.png`에서 확인한다.",
            "",
            "### 4.3 기관 수가 정원·신고인력에 제공하는 추가 정보",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["코드", "기관수-정원 ρ", "기관수-요양보호사 ρ", "정원 사용 상태"],
            [
                [
                    row["기관유형코드"],
                    format_number(row["기관수_정원_Spearman"]),
                    format_number(row["기관수_요양보호사_Spearman"]),
                    profiles.loc[
                        profiles["기관유형코드"].eq(row["기관유형코드"]),
                        "정원지표사용상태",
                    ].iloc[0],
                ]
                for _, row in b_summary.iterrows()
            ],
        )
    )
    lines.extend(
        [
            "",
            "이 상관은 기관 수와 정원·신고인력이 함께 움직이는 정도를 보여줄 뿐, "
            "기관 수가 제공역량을 원인적으로 증가시킨다는 뜻은 아니다. 신고인력은 "
            "고유 FTE가 아니며 서비스 유형 간 중복 가능성이 있다.",
            "",
            "## 5. 추론통계",
            "",
            "### 5.1 방법",
            "",
            "- 검정: 서비스별 Spearman 순위상관",
            "- 변수: 2022~2025 인정자 증가율과 2026년 인정자 1,000명당 기관 수",
            f"- 유의수준: {config['alpha']}",
            "- 다중검정: Benjamini–Hochberg FDR",
            "- 포함 조건: 완전 관측쌍 30개 이상, 공급지표 동률 50% 이하",
            "- 공급 0 지역: 기관 수 0으로 포함",
            "",
            "### 5.2 검정 결과",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["코드", "n", "Spearman ρ", "p값", "FDR p값", "FDR 0.05"],
            [
                [
                    row["기관유형코드"],
                    int(row["표본수"]),
                    format_number(row["통계량"]),
                    f"{float(row['p값']):.3g}",
                    f"{float(row['FDR보정p값']):.3g}",
                    "유의" if str(row["FDR_0.05기각"]) == "True" else "비유의",
                ]
                for _, row in tested.iterrows()
            ],
        )
    )
    significant_codes = ", ".join(significant["기관유형코드"].astype(str))
    lines.extend(
        [
            "",
            f"39개 서비스 중 14개를 검정했고 25개는 동률 비율 50% 초과로 "
            f"제외했다. FDR 보정 후 유의한 서비스는 6개({significant_codes})였다.",
            "",
            "유의한 6개 서비스의 상관 방향은 모두 양수였다. 이는 해당 서비스에서 "
            "인정수요 증가율이 높은 지역일수록 현재 인정자당 기관 수가 낮다는 예상과 "
            "반대 방향이다. 따라서 이번 단면 상관 결과는 가설 A의 예상 패턴을 "
            "지지하지 않는다.",
            "",
            "그러나 이 검정은 비교 가능한 연도별 공급 증가율을 직접 사용하지 못했다. "
            "따라서 `수요 증가가 공급 증가보다 빠르다`는 가설 전체를 채택하거나 "
            "기각할 수 없고, 현재 공급 수준과 수요 증가의 지역 연관성만 설명한다.",
            "",
            "## 6. 가설 판단",
            "",
            "| 가설 | 현재 판단 | 근거와 제한 |",
            "| --- | --- | --- |",
            "| A. 수요 증가가 공급 증가보다 빨라 반복 취약성이 나타남 | 보류 | 유의한 상관은 예상과 반대인 양의 방향. 비교 가능한 공급 성장률이 부족 |",
            "| B. 기관 수 외 정원·인력이 제공역량 차이를 설명 | 부분 지지 | 서비스별 정원·인력 분포 차이는 있으나 최신 현원·고유 FTE가 없음 |",
            "| C. 취약 우선배분이 균등배분보다 형평성을 개선 | 후속 시뮬레이션에서 판단 | 통계보고서에서는 시험 실행만 완료, 서비스·자원량 확정 필요 |",
            "| D·E. 실제 미충족수요와 접근·운영 문제가 원인 | 검증 불가 | 대기·이용거절·이동시간·운영시간 컬럼 없음 |",
            "",
            "## 7. 데이터 전처리 Python 코드와 역할",
            "",
            "원본 전처리는 [build_all_from_raw.py](../04_분석코드/build_all_from_raw.py), "
            "통계 분석은 [analyze_ltci_resource_allocation.py]"
            "(../04_분석코드/analyze_ltci_resource_allocation.py)가 실행한다. "
            "아래는 역할별 핵심 코드와 해석이다.",
            "",
            "### 7.1 전체 파일 읽기와 숫자형 변환",
            "",
            "```python",
            "frame = read_csv(path)",
            "frame = coerce_numeric(frame)",
            "```",
            "",
            "- 역할: Python이 CSV 전체 행을 읽고, 사전에 지정한 수치형 컬럼만 숫자로 변환한다.",
            "- 보호장치: 지역코드·날짜·Boolean 품질 플래그는 수치통계에서 제외한다.",
            "",
            "### 7.2 필수 컬럼·키·결측·중복 감사",
            "",
            "```python",
            "audit = audit_dataset(name, path, frame)",
            "```",
            "",
            "- 역할: 파일별 행·열·필수 컬럼·복합키 중복·결측·기간을 자동 검사한다.",
            "- 중단 조건: 필수 컬럼이나 키가 없으면 다음 단계로 진행하지 않는다.",
            "",
            "### 7.3 지역명 표준화",
            "",
            "```python",
            "standardized = standardize_region_columns(",
            "    frame, province_column, district_column, source, crosswalk=None",
            ")",
            "```",
            "",
            "- 역할: 시도 축약명, 복합시 일반구, 세종, 군위군 이동, 과거 지역명을 현행 시 단위로 맞춘다.",
            "- 검산: 수요·인구·1인세대·공급의 지역 결합률이 99% 미만이면 중단한다.",
            "",
            "### 7.4 일반구 공급 재집계와 공급 0 복원",
            "",
            "```python",
            "supply_agg = supply.groupby(",
            "    ['지역키', '기관유형코드', '기관유형명'], as_index=False",
            ")[value_columns].sum()",
            "complete_grid = regions.merge(service_master, how='cross')",
            "```",
            "",
            "- 역할: 일반구를 상위 시로 합산하고, 229개 지역×39개 서비스 전체 조합을 만든다.",
            "- 의미: 원 시설표에 없는 지역×서비스 조합을 공급 0 후보로 명시한다.",
            "- 검산: 집계 전후 기관·정원·직종별 인력 총합이 같아야 한다.",
            "",
            "### 7.5 수요 불확실성과 공급지표",
            "",
            "```python",
            "recognized_mid = (recognized_lower + recognized_upper) / 2",
            "rate = institutions / recognized_mid * 1000",
            "```",
            "",
            "- 역할: 비공개 인정자 값을 0으로 바꾸지 않고 하한·중앙·상한 세 조건의 공급률을 계산한다.",
            "- 제한: 인정자는 서비스 유형별 실제 이용자 수가 아니다.",
            "",
            "### 7.6 서비스별 정원 사용 규칙",
            "",
            "```python",
            "capacity_rate = capacity_rate.where(capacity_metric_usable)",
            "```",
            "",
            "- 역할: 방문요양·방문목욕·방문간호·복지용구에는 정원지표를 적용하지 않는다.",
            "- 조건부 처리: 정원형 서비스도 자료 충족률 80% 미만이면 사용을 보류한다.",
            "",
            "### 7.7 추론통계와 다중검정",
            "",
            "```python",
            "rho, p_value = spearmanr(demand_growth, supply_rate)",
            "adjusted_p = benjamini_hochberg(p_values)",
            "```",
            "",
            "- 역할: 서비스별 순위상관을 계산하고 반복검정의 거짓발견률을 보정한다.",
            "- 제외 규칙: 완전 관측쌍 30개 미만 또는 동률 50% 초과 서비스는 검정하지 않는다.",
            "- 해석: 상관은 원인이나 정책효과가 아니다.",
            "",
            "## 8. 한계와 다음 단계",
            "",
            "- 2026년 현재 현원·대기자·이용거절이 없다.",
            "- 신고인력은 고유 FTE가 아니다.",
            "- 공급자료의 공개시점과 생성방식이 일정하지 않아 완전한 공급 성장률을 만들기 어렵다.",
            "- 희소서비스 25개는 지역 공급 0이 많아 순위검정에 적합하지 않다.",
            "- B01은 수요 하한·상한에 따른 지역순위 안정성이 낮아 세 조건을 별도로 보고해야 한다.",
            "- 다음 단계에서는 주요 서비스 범위를 먼저 확정하고 하한·중앙·상한 및 취약기준 20%·25%·30% 민감도를 비교한다.",
            "",
            "## 9. 재현 파일",
            "",
            "- 원본 전처리 코드: [`build_all_from_raw.py`](../04_분석코드/build_all_from_raw.py)",
            "- 전처리·통계 코드: [`analyze_ltci_resource_allocation.py`](../04_분석코드/analyze_ltci_resource_allocation.py)",
            "- 원본-산출물 계보·해시: `outputs/raw_preprocessing/lineage_manifest.json`",
            "- 분석 전 검사: [`check_preanalysis_readiness.py`](../04_분석코드/check_preanalysis_readiness.py)",
            "- 통계 준비 검사: [`check_statistical_readiness.py`](../04_분석코드/check_statistical_readiness.py)",
            "- 통계 설정: `config/statistical_config.json`",
            "- 기술통계: `outputs/analysis/descriptive_statistics.csv`",
            "- 서비스 프로파일: `outputs/statistical_readiness/service_statistical_profiles.csv`",
            "- 가설 기술통계: `outputs/analysis/hypothesis_descriptive_results.csv`",
            "- 추론통계: `outputs/analysis/hypothesis_inference_results.csv`",
            "- 분포 그림: `outputs/analysis/supply_rate_distributions.png`",
            "",
        ]
    )

    preprocessing_script = (
        ROOT.parent / "04_분석코드" / "build_all_from_raw.py"
    ).read_text(encoding="utf-8")
    xlsx_extractor_script = (
        ROOT.parent / "04_분석코드" / "extract_xlsx_sheet.py"
    ).read_text(encoding="utf-8")
    time_series_script = (
        ROOT.parent / "04_분석코드" / "build_core_time_series.py"
    ).read_text(encoding="utf-8")
    analysis_script = (
        ROOT.parent / "04_분석코드" / "analyze_ltci_resource_allocation.py"
    ).read_text(encoding="utf-8")
    lines.extend(
        [
            "## 10. 코드 실행 위치",
            "",
            "전체 코드의 역할·입력·출력·실행 명령은 "
            "[분석 코드 목차](../04_분석코드/README.md)에 정리했다.",
            "",
            "| 단계 | 실행 파일 | 생성·확인 내용 |",
            "| --- | --- | --- |",
            "| 원본 재구축 | [build_all_from_raw.py](../04_분석코드/build_all_from_raw.py) | 원본에서 전처리 파일과 계보표 생성 |",
            "| 분석 전 검사 | [check_preanalysis_readiness.py](../04_분석코드/check_preanalysis_readiness.py) | 컬럼·중복·총량·완전성·시점 정합성 검사 |",
            "| 통계 전 검사 | [check_statistical_readiness.py](../04_분석코드/check_statistical_readiness.py) | 분포·표본수·희소성과 검정 가능성 검사 |",
            "| 통계·시뮬레이션 | [analyze_ltci_resource_allocation.py](../04_분석코드/analyze_ltci_resource_allocation.py) | 지표·통계·배치 시나리오 계산 |",
            "| 보고서 생성 | [generate_statistical_report.py](../04_분석코드/generate_statistical_report.py) | 결과를 현재 보고서로 변환 |",
            "",
            "## 11. 전처리·기술통계·추론통계 전체 Python 코드",
            "",
            "아래 두 코드는 이번 결과를 생성한 실제 실행 파일의 전체 내용이다. "
            "첫 번째 코드가 공개 원본에서 분석용 표를 만들고, 두 번째 코드가 그 표를 "
            "검산한 뒤 통계를 계산한다.",
            "",
            "실행 명령:",
            "",
            "```powershell",
            r"python ""04_분석코드/build_all_from_raw.py""",
            r"python ""04_분석코드/analyze_ltci_resource_allocation.py"" "
            r"--stage hypotheses --run-inference",
            "```",
            "",
            "코드는 원본 추출, 인코딩, 지역·연령 집계, 입력·스키마 검사, "
            "전처리 검산, 기술통계, 추론통계, 선택적 시뮬레이션 순으로 구성했다. "
            "비슷해 보이는 검산문은 "
            "누락·잘못된 지역 결합·집계 총량 변화를 차단하는 서로 다른 검사이므로 "
            "삭제하지 않았다.",
            "",
            "### 11.1 원본에서 분석용 표를 만드는 전체 코드",
            "",
            "```python",
            preprocessing_script.rstrip(),
            "```",
            "",
            "### 11.2 XLSX 원본 시트 추출 코드",
            "",
            "```python",
            xlsx_extractor_script.rstrip(),
            "```",
            "",
            "### 11.3 원본 시계열 표 생성 코드",
            "",
            "```python",
            time_series_script.rstrip(),
            "```",
            "",
            "### 11.4 분석용 표 검산과 통계 전체 코드",
            "",
            "```python",
            analysis_script.rstrip(),
            "```",
            "",
        ]
    )

    report_path = REPORT_DIR / "07_기술통계와_추론통계_분석보고서.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(report_path)
    print(
        json.dumps(
            {
                "기술통계서비스": len(profiles),
                "추론검정서비스": len(tested),
                "추론제외서비스": len(excluded),
                "FDR유의서비스": len(significant),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
