# Python 분석 실행 전 계획

이 문서는 [`../../04_분석코드/analyze_ltci_resource_allocation.py`](../../04_분석코드/analyze_ltci_resource_allocation.py)를 실제 실행하기 전에
입력·계산·출력·중단 조건을 검토하기 위한 문서다. 아직 분석 결과를 의미하지 않는다.

## 0. 분석 환경

- 가상환경: `.venv-analysis`
- Python: 시스템 Python 3.13 기반의 프로젝트 전용 환경
- 설치 확인: NumPy 2.5.1, pandas 2.3.3, SciPy 1.18.0, Matplotlib 3.11.1
- 의존성 파일: `requirements-analysis.txt`
- Git 제외: 가상환경, Python 캐시, 분석 출력 폴더

```powershell
# 가상환경 Python 확인
.\.venv-analysis\Scripts\python.exe --version

# 패키지 설치 또는 재설치
.\.venv-analysis\Scripts\python.exe -m pip install `
  -r requirements-analysis.txt
```

## 1. 실행 순서

| 단계 | 명령의 `--stage` | 계산 내용 | 주요 출력 |
| --- | --- | --- | --- |
| 1 | `audit` | 행·열·필수 컬럼·키 중복·결측·기간 | `data_quality_audit.csv`, `variable_dictionary.csv` |
| 2 | `describe` | 평균·중앙값·범위·사분위수·표준편차·변동계수 | `descriptive_statistics.csv` |
| 3 | `metrics` | 수요 하한·중앙·상한별 지역×서비스 공급지표 | `current_region_service_metrics.csv` |
| 4 | `hypotheses` | 가설 A·B의 기술통계와 선택적 Spearman 상관 | `hypothesis_descriptive_results.csv` |
| 5 | `simulation` | 균등·수요비례·취약우선·형평성 기준 배치 | `simulation_detail_*.csv`, `simulation_summary_*.csv` |

## 2. 주요 지표

- 인정자 1,000명당 기관 수
- 인정자 1,000명당 정원
- 인정자 1,000명당 요양보호사 신고인력
- 75세 이상 인구 1,000명당 기관 수
- 고령 1인세대 1,000세대당 기관 수
- 기관 1곳당 인정자
- 2022~2025 인정자 증가율과 연평균 증가율
- 공급 하위 25% 탐색 후보
- 시나리오별 평균·중앙·최저 공급률, 지니계수, Theil 지수

## 3. 자동 중단 조건

- 필수 파일 또는 필수 컬럼이 없음
- 데이터셋의 복합키 컬럼이 없음
- 수요·인구·1인세대·공급 중 최저 지역 결합률이 99% 미만
- 시뮬레이션의 추가 자원 합계가 입력값과 다름
- 음수 추가 자원 또는 존재하지 않는 서비스 코드를 입력

중복키는 감사표에 기록한다. 실제로 중복이 허용되지 않는 분석용 파일에서 중복이
발견되면 원인을 확인한 뒤 다음 단계 실행 여부를 결정한다.

## 4. 통계 사용 원칙

- 핵심자료는 전국 행정자료이므로 기술통계와 효과크기·민감도를 우선한다.
- 추론통계는 기본적으로 실행하지 않는다.
- `--run-inference`를 명시한 경우에만 Spearman 순위상관을 계산한다.
- p값만으로 가설을 채택하지 않고 효과크기·분포·민감도와 함께 해석한다.
- 기관 상세 API 1,600건은 비확률표본이므로 모집단 추론에서 제외한다.
- 현재 컬럼이 없는 미충족수요·접근성 가설 D·E는 통계검정을 하지 않는다.

## 5. 실행 전 확인할 결정

1. 지역 대응표를 먼저 확정할지, 감사 단계에서 미결합 지역을 확인한 뒤 만들지
2. 첫 시뮬레이션 대상 기관유형코드
3. 추가 기관 수
4. 탐색용 취약 기준을 하위 25%로 둘지
5. 추론통계를 이번 분석에 포함할지

## 6. 예정 실행 명령

```powershell
# 1단계: 데이터 감사만 실행
python "04_분석코드/analyze_ltci_resource_allocation.py" --stage audit

# 2단계: 기술통계
python "04_분석코드/analyze_ltci_resource_allocation.py" --stage describe

# 3단계: 표준 지역명 규칙을 적용한 핵심 지표
python "04_분석코드/analyze_ltci_resource_allocation.py" `
  --stage metrics

# 4단계: 기술통계 기반 가설 확인
python "04_분석코드/analyze_ltci_resource_allocation.py" `
  --stage hypotheses

# 추론통계는 사용자가 확인한 후에만 별도 실행
python "04_분석코드/analyze_ltci_resource_allocation.py" `
  --stage hypotheses `
  --run-inference

# 5단계: 서비스 코드와 추가 자원 수를 확정한 뒤 실행
python "04_분석코드/analyze_ltci_resource_allocation.py" `
  --stage simulation `
  --service-code B01 `
  --additional-units 10
```

## 7. 해석 제한

- 하위 25%는 공식 부족 기준이 아니라 탐색용 기준이다.
- 인정자는 서비스 유형별 실제 이용수요가 아니다.
- 신고인력은 고유 종사자 또는 FTE가 아니다.
- 시뮬레이션은 공급지표 변화이며 실제 대기·이용·복지성과 예측이 아니다.
