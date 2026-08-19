# 돌봄자원 랩 대시보드

도 소속 76개 군의 장기요양 공급격차와 자원배치 전략을 탐색하는 포트폴리오형 대시보드입니다.

[Live Dashboard](https://dlthdl321-rgb.github.io/) · [Case Study](../CASE_STUDY.md) · [분석방법론](../02_분석보고서/01_분석방법론.md)

## 제공 화면

- 프로젝트 소개와 실데이터 기반 핵심 발견
- 76개 군 지역별 비교와 한 장 진단서
- 자원 추가·감축·이전 시뮬레이션
- 과거·미래 변화와 자동배치 민감도
- 외부공급 기여관계, 보고서와 데이터 품질

“기관 미관측”은 공개자료에서 기관이 확인되지 않았다는 뜻이며 실제 기관 부재를 확정하지 않습니다. 탐색기준과 접근성 가중치는 정책 확정값이 아닌 탐색 입력입니다.

## 코드 구조

- index.html → 브라우저가 처음 읽는 표준 Vite HTML
- src/main.tsx → React 진입점
- src/App.tsx → 전역 데이터·공유 상태·상위 화면 구성
- src/views/ → 화면별 표현
- src/components/ → 여러 화면에서 재사용하는 UI
- src/lib/data.ts → JSON 로딩과 CSV 저장
- src/lib/format.ts → 숫자와 자원 단위 formatting
- src/lib/allocation.ts → canonical Python 규칙과 동등한 자동 자원배치 계산
- src/lib/timeline.ts → 연도별 수요·자원 시나리오 계산
- src/types.ts → 공통 데이터 타입
- public/data/ → 분석 코드가 생성하고 Dashboard가 읽는 공개 JSON

## 실행

Node.js 22.13 이상이 필요합니다.

```bash
npm install
npm run dev
```

개발 서버는 Vite가 `index.html → src/main.tsx → src/App.tsx` 경로를 실행합니다.

## 검증과 빌드

```bash
npm run check
npm run build
npm run preview
```

- `npm run check`: lint 후 정적 빌드·데이터·공개 문구 회귀검사
- `npm run build`: dist-public/에 GitHub Pages용 정적 산출물 생성
- `npm run preview`: 빌드 결과를 로컬에서 확인

## 데이터 갱신

대시보드의 `public/data/*.json`은 저장소 분석 산출물에서 생성됩니다. 원본·중간·결과 파일의 계보는 상위 경로의 [`03_데이터/README.md`](../03_데이터/README.md), 분석 재현은 [`04_분석코드/README.md`](../04_분석코드/README.md)를 참고하세요.

```bash
python scripts/prepare_dashboard_data.py
```

## 배포

GitHub Pages는 `npm run build`가 생성한 dist-public/을 배포합니다. 배포 URL은 상위 [`README.md`](../README.md)에 기록합니다.
