# 데이터 안내

## 공개한 데이터

| 폴더 | 단계 | 용도 |
| --- | --- | --- |
| `analysis_ready/` | 분석 테이블 | 지역·연도·서비스 단위의 지표 계산과 통계분석 |
| `processed/` | 전처리 결과 | 분석 테이블의 생성 과정 확인과 재현 |
| `catalog/` | 보완 목록 | 정책 시행지역·시점 등 분석 설계 보조 |

주요 출처는 국민건강보험공단, 건강보험심사평가원, 행정안전부 주민등록 인구통계, KOSIS, 한국사회보장정보원 등입니다. 파일별 출처·기준일·변환 내용은 [`../metadata/`](../metadata/)와 [`catalog/`](catalog/)에서 확인할 수 있습니다.

## 현재 핵심 분석파일

| 파일 | 행 수 | 기준기간 | 핵심 컬럼 |
| --- | ---: | --- | --- |
| `analysis_ready/elderly_population_sigungu_202606.csv` | 255 | 2026-06 | `총인구`, `65세이상인구`, `85세이상인구`, `고령화율` |
| `analysis_ready/elderly_single_person_households_sigungu_202606.csv` | 255 | 2026-06 | `65세이상1인세대` |
| `analysis_ready/ltci_demand_sigungu_bounds_202605.csv` | 235 | 2026-05-31 | `인정자_추정하한`, `인정자_추정상한` |
| `analysis_ready/ltci_supply_sigungu_service_type_20260610.csv` | 3,600 | 2026-06-10 | `기관유형코드`, `기관수`, `정원`, 직종별 신고인력 |
| `analysis_ready/ltci_supply_snapshots_202310_202606.csv` | 18,567 | 4개 공개시점 | 기관·정원·현원·신고인력 |
| `analysis_ready/annual_ltci_benefit_sigungu_2013_2024.csv` | 28,629 | 2013~2024년 | `service_type`, `benefit_users`, `service_days`, 급여비 |
| `analysis_ready/monthly_elderly_population_sigungu_2016_2025.csv` | 32,313 | 2016-01~2025-12 | 월별 총인구·65세·75세·85세 이상 인구 |

행 수와 컬럼은 2026-07-24에 Python으로 전체 파일을 읽어 다시 확인했습니다. 전체 스키마 목록은 [`../metadata/current_schema_audit.json`](../metadata/current_schema_audit.json)에서 확인할 수 있습니다.

## 포함하지 않은 데이터

- `data/raw/`: 대용량 원본 API 응답과 원본 압축파일
- 인증키가 포함될 수 있는 설정파일
- 제3자 저작권이 적용되는 논문 PDF 원문

수집·전처리 스크립트는 [`../../04_분석코드/`](../../04_분석코드/)에 있으며 인증키는 환경변수로 주입해야 합니다.

## 해석 주의사항

- 자료별 기준일과 공개주기가 서로 다릅니다.
- 기관 신고 인력은 실제 근무시간이나 가용 인력과 다를 수 있습니다.
- 기관 수가 같아도 정원, 인력, 이용량의 병목은 다를 수 있습니다.
- 공개 집계자료만으로 실제 미충족 수요 인원이나 정책의 인과효과를 확정할 수 없습니다.
