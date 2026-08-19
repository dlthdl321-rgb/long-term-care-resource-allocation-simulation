# Dashboard dataset lineage

Dashboard가 초기 로드하는 JSON의 역할과 재현 상태를 정리합니다. `prepare_dashboard_data.py`는 tracked 입력만 사용하며, 탐색적 확장분석 스냅숏은 임의로 역산하지 않습니다.

| Dataset | 사용 화면 | 생성기·입력 | 상태 |
| --- | --- | --- | --- |
| `baseline` | 진단·What-if·자동배치 | canonical 분석 기준선에서 고정한 공개 snapshot | canonical frozen snapshot |
| `regions` | Overview·지역비교·취약성 | canonical 76개 군 지역지표 공개 snapshot | canonical frozen snapshot |
| `workforce` | 지역진단 | `prepare_dashboard_data.py` ← tracked `analysis_ready/ltci_supply_sigungu_service_type_20260610.csv` | 재현 가능 |
| `history` | 과거·미래 변화 | `prepare_dashboard_data.py` ← tracked 인구·인정수요 연말 패널 | 재현 가능 |
| `quality` | 보고서·품질 안내 | `prepare_dashboard_data.py`의 공개 기준일·주의문 | 재현 가능 |
| `portfolio-summary` | Overview | `prepare_dashboard_data.py` ← `baseline` + 대표 scenario metrics | 재현 가능 |
| `supply-trends` | 과거·미래 변화 | 분석 당시 시계열 계산 결과 | exploratory frozen snapshot |
| `stability` | 민감도 | 분석 당시 민감도 계산 결과 | exploratory frozen snapshot |
| `access-regions` | 외부공급 | 같은 도 접근성 가정의 지역별 결과 | exploratory frozen snapshot |
| `access-metrics` | 외부공급 | 같은 도 접근성 가정의 요약 결과 | exploratory frozen snapshot |
| `access-impact` | What-if 직접·간접 영향 | 같은 도 접근성 가정의 영향 결과 | exploratory frozen snapshot |
| `access-contributions` | 외부공급 상세 | 같은 도 접근성 가정의 출발·도착 기여관계 | exploratory frozen snapshot |

Frozen snapshot은 현재 UI의 탐색적 확장분석을 재현하는 공개 산출물이지만, tracked 입력만으로 다시 생성할 수 있다고 주장하지 않습니다. 대표 네 배치전략은 snapshot이 아니라 `src/lib/allocation.ts`에서 계산되며 Python 산출물과 parity test로 검증합니다.
