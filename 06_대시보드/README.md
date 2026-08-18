# 돌봄자원 랩 대시보드

도 소속 76개 군의 장기요양 공급격차와 자원배치 전략을 탐색하는 포트폴리오형 대시보드입니다.

## 제공 화면

- 프로젝트 소개와 실데이터 기반 핵심 발견
- 76개 군 지역별 비교와 한 장 진단서
- 자원 추가·감축·이전 시뮬레이션
- 과거·미래 변화와 자동배치 민감도
- 외부공급 기여관계, 보고서와 데이터 품질

“기관 미확인”은 공개자료에서 기관이 확인되지 않았다는 뜻이며 실제 기관 부재를 확정하지 않습니다. 목표와 접근성 가중치는 정책 확정값이 아닌 탐색 입력입니다.

## 실행

Node.js 22.13 이상이 필요합니다.

```bash
npm install
npm run dev
```

## 검증과 빌드

```bash
npm test
npm run lint
npm run build:public
```

- `npm test`: 배포 빌드와 서버 렌더링·데이터 완전성 검사
- `npm run lint`: TypeScript/React 정적 검사
- `npm run build:public`: GitHub Pages 등에 올릴 수 있는 정적 빌드

## 데이터 갱신

대시보드의 `public/data/*.json`은 저장소 분석 산출물에서 생성됩니다. 원본·중간·결과 파일의 계보는 상위 경로의 [`03_데이터/README.md`](../03_데이터/README.md), 분석 재현은 [`04_분석코드/README.md`](../04_분석코드/README.md)를 참고하세요.

## 배포

연결된 Sites 프로젝트 설정은 `.openai/hosting.json`에 있습니다. 배포 URL은 상위 [`README.md`](../README.md)에 기록합니다.
