# 분석 코드 목차

모든 명령은 **저장소 최상위 폴더**에서 실행합니다. 코드 내부의 [`project_paths.py`](project_paths.py)가 `03_데이터`의 입력·설정·출력 경로를 고정하므로 현재 작업 폴더에 의존하지 않습니다.

## 권장 실행 순서

```bash
python -m venv .venv
pip install -r requirements.txt
python "04_분석코드/check_preanalysis_readiness.py"
python "04_분석코드/check_statistical_readiness.py"
python "04_분석코드/analyze_ltci_resource_allocation.py" --stage metrics
python "04_분석코드/analyze_hypothesis_testing.py"
python "04_분석코드/simulation/run_allocation_scenarios.py"
```

원본 데이터를 다시 수집할 때만 수집 코드를 먼저 실행합니다. API 수집 코드는 공공데이터포털의 `DATA_GO_KR_SERVICE_KEY` 또는 KOSIS의 `KOSIS_API_KEY` 환경변수가 필요할 수 있습니다.

## 1. 공통 경로

| 코드 | 실행 단계 | 역할 |
| --- | --- | --- |
| [`project_paths.py`](project_paths.py) | 모든 단계에서 자동 호출 | 데이터, 결과, 설정, 보고서, 선행연구 폴더의 절대경로를 한곳에서 정의합니다. 직접 실행하지 않습니다. |

## 2. 원본자료 수집

| 코드 | 실행 위치·방법 | 주요 입력 | 주요 출력과 역할 |
| --- | --- | --- | --- |
| [`download_data_go_kr_ltci_history.py`](download_data_go_kr_ltci_history.py) | `python "04_분석코드/download_data_go_kr_ltci_history.py"` | 공공데이터포털 과거파일 페이지 | 장기요양 등급판정 과거 CSV를 `03_데이터/data/raw/`에 수집하고 해시를 기록합니다. |
| [`download_kosis_ltci_benefit_history.py`](download_kosis_ltci_benefit_history.py) | `python "04_분석코드/download_kosis_ltci_benefit_history.py"` | KOSIS 대량통계 | 시군구별 장기요양 급여실적 ZIP을 연도별로 수집합니다. |
| [`download_kosis_required_raw.py`](download_kosis_required_raw.py) | `python "04_분석코드/download_kosis_required_raw.py"` | `KOSIS_API_KEY` | 연구에 필요한 기관·인력·정원 통계 원본과 수집 명세를 저장합니다. |
| [`download_mois_monthly_age_population.py`](download_mois_monthly_age_population.py) | `python "04_분석코드/download_mois_monthly_age_population.py"` | 행정안전부 주민등록 인구통계 | 3개월 단위 시군구 연령별 인구 원본과 검산표를 저장합니다. |
| [`collect_hira_nursing_hospital_details.py`](collect_hira_nursing_hospital_details.py) | `python "04_분석코드/collect_hira_nursing_hospital_details.py"` | HIRA 인증키, 요양병원 목록 | 요양병원의 시설·인력·전문진료 세부정보를 수집합니다. |
| [`collect_ltci_institutional_occupancy.py`](collect_ltci_institutional_occupancy.py) | `python "04_분석코드/collect_ltci_institutional_occupancy.py"` | 공공데이터포털 인증키, 장기요양기관 목록 | 시설급여기관의 정원·현원 세부정보와 수집 명세를 저장합니다. |
| [`collect_ltci_detail_sample.py`](collect_ltci_detail_sample.py) | `python "04_분석코드/collect_ltci_detail_sample.py" --input <기관목록> --output-dir <저장폴더>` | 기관 목록과 인증키 | API 할당량을 고려해 지역·기관유형별 표본의 시설·인력·프로그램 정보를 수집합니다. |
| [`collect_social_welfare_facility_list.ps1`](collect_social_welfare_facility_list.ps1) | `powershell -File "04_분석코드/collect_social_welfare_facility_list.ps1" -ServiceKey <인증키>` | 공공데이터포털 인증키 | 사회복지시설 XML을 페이지별 저장하고 분석용 CSV로 변환합니다. |

## 3. 전처리와 분석 테이블 생성

| 코드 | 실행 위치·방법 | 주요 입력 | 주요 출력과 역할 |
| --- | --- | --- | --- |
| [`extract_xlsx_sheet.py`](extract_xlsx_sheet.py) | 다른 전처리 코드에서 호출하거나 인자를 지정해 실행 | 원본 XLSX와 시트명 | 지정 시트를 CSV로 추출하는 공통 도구입니다. |
| [`build_all_from_raw.py`](build_all_from_raw.py) | `python "04_분석코드/build_all_from_raw.py"` | `03_데이터/data/raw/` | 원본부터 주요 전처리 파일을 다시 만들고 SHA-256 계보표를 생성합니다. |
| [`build_analysis_ready.ps1`](build_analysis_ready.ps1) | `powershell -File "04_분석코드/build_analysis_ready.ps1"` | 기관·인구 전처리 파일 | 시군구 단위 인구·공급 분석 테이블을 생성합니다. |
| [`build_pre_analysis_tables.ps1`](build_pre_analysis_tables.ps1) | `powershell -File "04_분석코드/build_pre_analysis_tables.ps1"` | 행정구역·인구·수요·공급 자료 | 지역 기준표와 분석 전 결합 테이블을 생성합니다. |
| [`build_core_time_series.py`](build_core_time_series.py) | `python "04_분석코드/build_core_time_series.py"` | 시설현황 과거자료 | 기관·정원·인력의 시점별 자료를 표준화해 공급 스냅숏 패널로 만듭니다. |
| [`build_kosis_ltci_benefit_panel.py`](build_kosis_ltci_benefit_panel.py) | `python "04_분석코드/build_kosis_ltci_benefit_panel.py"` | KOSIS 급여실적 원본 | 2013~2024년 시군구×급여종류 패널과 품질검사 결과를 만듭니다. |
| [`build_ltci_service_outcome_panel.py`](build_ltci_service_outcome_panel.py) | `python "04_분석코드/build_ltci_service_outcome_panel.py"` | 장기요양 급여 패널 | 재가·시설 서비스 이용자와 제공일수 결과지표를 파생합니다. |
| [`build_mois_monthly_elderly_panel.py`](build_mois_monthly_elderly_panel.py) | `python "04_분석코드/build_mois_monthly_elderly_panel.py"` | 주민등록 연령별 월간 원본 | 시군구 월별 고령인구 패널과 파일별 검산표를 만듭니다. |

## 4. 품질검사·통계·시뮬레이션

| 코드 | 실행 위치·방법 | 주요 입력 | 주요 출력과 역할 |
| --- | --- | --- | --- |
| [`check_preanalysis_readiness.py`](check_preanalysis_readiness.py) | `python "04_분석코드/check_preanalysis_readiness.py"` | 분석용 수요·인구·공급 패널 | 필수 컬럼, 중복, 완전격자, 총량, 분모, 시점 정합성과 재현성을 검사합니다. |
| [`check_statistical_readiness.py`](check_statistical_readiness.py) | `python "04_분석코드/check_statistical_readiness.py"` | 분석 테이블과 통계 설정 | 변수 분포·표본수·희소성·검정 가능성을 확인하고 서비스별 통계 프로파일을 만듭니다. |
| [`analyze_ltci_resource_allocation.py`](analyze_ltci_resource_allocation.py) | `python "04_분석코드/analyze_ltci_resource_allocation.py" --stage metrics` | 분석용 데이터와 설정 | 데이터 감사·기술통계·기준선 공급지표를 생성합니다. `hypotheses`·`simulation`·`all`은 과거 산출물 재현용 호환 단계이며 최종 결과의 기준 구현이 아닙니다. |
| [`analyze_hypothesis_testing.py`](analyze_hypothesis_testing.py) | `python "04_분석코드/analyze_hypothesis_testing.py"` | 76개 군의 수요·인구·공급 테이블 | **최종 가설검정의 단일 기준 구현**입니다. 대표 Spearman·bootstrap·BH-FDR 결과를 `outputs/hypothesis_testing/`에 생성합니다. |
| [`simulation/run_allocation_scenarios.py`](simulation/run_allocation_scenarios.py) | `python "04_분석코드/simulation/run_allocation_scenarios.py"` | `representative_allocation_scenario.json`과 분석용 공급자료 | **대표 배치 결과의 단일 기준 구현**입니다. 방문간호기관 5개소의 네 전략 결과를 생성합니다. 상세 설정은 [시뮬레이션 README](simulation/README.md)를 따릅니다. |
| [`archive/generate_statistical_report.py`](archive/generate_statistical_report.py) | 현재 실행경로에서 제외 | 과거 통계·검증 산출물 | 이전 전국 범위의 통계보고서를 생성하던 레거시 도구입니다. 현재 방법론의 기준 문서 생성 도구가 아닙니다. |
| [`extract_literature_indicator_context.py`](extract_literature_indicator_context.py) | `python "04_분석코드/extract_literature_indicator_context.py"` | `05_선행연구자료/`의 PDF | 선행연구에서 지표 관련 문맥을 추출하는 보조 코드입니다. 공개 저장소에는 PDF 원문을 포함하지 않습니다. |

## 테스트

대표 배치 엔진의 총량 보존, 비음수, 필요량·지역상한과 전략 간 기준선 독립성을 검사합니다.

```bash
python -m unittest discover -s "04_분석코드/simulation" -p "test_*.py" -v
```

## 결과 해석 범위

코드는 공개 집계자료에 근거한 기술통계·추론통계와 규칙 기반 배치 시뮬레이션을 수행합니다. 결과는 우선 확인할 지역과 배치 대안을 비교하는 근거이며, 실제 정책의 인과효과나 개인 수준의 건강 개선을 직접 증명하지 않습니다.

현재 수행 정의와 해석 기준은 [분석방법론](../02_분석보고서/01_분석방법론.md)을 참고하세요. 이 문서는 실행과 재현 절차만을 담당합니다.
