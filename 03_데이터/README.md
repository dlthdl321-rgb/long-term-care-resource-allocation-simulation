# 데이터 구조와 계보

이 문서는 데이터의 출처·기준시점·저장 단계와 품질 기록을 안내합니다. 분석 정의와 결과 해석은 [분석방법론](../02_분석보고서/01_분석방법론.md), 실행 명령은 [분석 코드 README](../04_분석코드/README.md)를 따릅니다.

## 데이터 흐름

```text
공개 원자료·API
→ data/catalog·data/processed
→ data/analysis_ready
→ 품질검사
→ outputs/analysis·outputs/day05_hypothesis_testing·outputs/q4a_mvp
→ Dashboard public data
```

| 경로 | Grain·역할 |
| --- | --- |
| [`data/catalog/`](data/catalog/) | 수집 대상과 원천자료 목록 |
| [`data/processed/`](data/processed/) | 지역·시점·서비스 표기를 표준화한 중간자료 |
| [`data/analysis_ready/`](data/analysis_ready/) | 시군구, 시군구×서비스 또는 시군구×시점 분석 테이블 |
| [`config/`](config/) | 분석 모집단·목표·시뮬레이션 입력 설정 |
| [`metadata/`](metadata/) | 출처, 수집일, 기준일, 스키마 감사와 SHA-256 |
| [`outputs/`](outputs/) | 품질검사·기술통계·추론통계·시뮬레이션 결과 |

## 대표 분석 입력

| 파일 | 출처·기준일 | Grain | 주요 컬럼 |
| --- | --- | --- | --- |
| `elderly_population_sigungu_202606.csv` | 행정안전부, 2026년 6월 | 시군구 | 총인구, 65세 이상 인구, 고령화율 |
| `elderly_single_person_households_sigungu_202606.csv` | 행정안전부, 2026년 6월 | 시군구 | 65세 이상 1인세대 |
| `ltci_demand_sigungu_bounds_202605.csv` | 국민건강보험공단, 2026년 5월 | 시군구 | 인정자 추정 하한·상한 |
| `ltci_supply_sigungu_service_type_20260610.csv` | 장기요양 공개자료, 2026-06-10 | 시군구×기관유형 | 기관수, 정원, 직종별 신고인력 |
| `ltci_supply_snapshots_202310_202606.csv` | 장기요양 공개자료, 2023-10~2026-06 | 시점×시군구×기관유형 | 기관·정원·인력 스냅숏 |
| `annual_ltci_benefit_sigungu_2013_2024.csv` | KOSIS, 2013~2024년 | 연도×시군구×급여종류 | 이용자, 제공일수, 급여비, 제공기관 수 |

전체 파일과 세부 출처는 [`data/README.md`](data/README.md), [`data/catalog/README.md`](data/catalog/README.md)와 `metadata/`의 데이터별 기록을 확인합니다.

## 결측·비공개와 품질

- 인정자 비공개 셀은 공개값과 섞지 않고 추정 하한·상한·중앙값을 분리합니다.
- 실제 0, 원자료 미관측, 비공개 상태는 서로 다른 값으로 유지합니다.
- 기관 미관측은 공개자료에서 해당 지역×서비스 조합을 확인하지 못했다는 뜻이며 실제 기관 부재를 확정하지 않습니다.
- 필수 컬럼, 키 중복, 지역코드, 완전격자, 결합률, 총량과 기준시점 차이를 품질검사에서 확인합니다.
- 수집·변환 파일의 해시는 [`metadata/checksums_sha256.csv`](metadata/checksums_sha256.csv), 스키마 감사는 `metadata/current_schema_audit.json`에 기록합니다.
- 분석 변수의 이름·단위·해석은 [`outputs/validation/variable_dictionary.csv`](outputs/validation/variable_dictionary.csv)를 사용합니다.

원천자료를 저장소에 포함하지 않은 경우에는 수집 코드와 metadata의 출처·수집 조건으로 계보를 유지합니다. 원본·중간·분석용·결과 파일을 같은 파일로 덮어쓰지 않습니다.
