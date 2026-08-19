import { fmt } from "./lib/format";

export type View =
  | "overview" | "regions" | "diagnosis" | "field" | "simulator"
  | "timeline" | "sensitivity" | "access" | "reports";

export const VIEW_GUIDES: Record<View, { title: string; summary: string; terms: [string, string][] }> = {
  overview: { title: "처음이라면 여기부터 보세요", summary: "먼저 살펴볼 지역과 부족한 서비스의 전체 그림입니다. 숫자는 실제 확정 필요량이 아니라, 같은 기준으로 지역을 비교한 계산 결과입니다.", terms: [["기관 미관측", "공개자료에서 해당 서비스 기관이 관측되지 않은 경우"], ["탐색기준 미만", "현재 공급이 군 분포의 중앙값 기준에 못 미치는 경우"], ["탐색용 검토 순서", "현장 확인을 어디부터 시작할지 돕는 비교 순서"]] },
  regions: { title: "지역 순위를 읽는 법", summary: "선택한 정렬기준이 높은 지역이 위에 표시됩니다. 종합 탐색순서는 여러 지표를 함께 본 보조 검토순서입니다.", terms: [["돌봄수요 부담", "장기요양 인정자 규모와 증가 흐름을 합친 비교점수"], ["공급격차 점수", "기관·서비스 제공인력·정원이 탐색기준보다 낮은 정도"], ["탐색용 순서", "자원 배분 확정 순위가 아닌 현장검토 시작 순서"]] },
  diagnosis: { title: "한 지역의 근거를 한 장에서 확인하세요", summary: "인구·장기요양 수요·현재 자원·직종별 인력·부족도·외부공급을 한곳에 모았습니다. 숫자 옆의 기준일과 경고까지 함께 확인하세요.", terms: [["현재 자원", "최신 공개자료에서 집계된 기관·인력·정원"], ["서비스 제공인력", "서비스별 분석에 사용한 주요 종사자 합계"], ["한 장 진단서", "배치 확정서가 아닌 현장확인을 위한 근거 요약"]] },
  field: { title: "결과를 실제 검토업무로 연결하세요", summary: "자동 결론과 검토문구를 먼저 읽고, 현실적인 사전 시나리오와 탐색기준별 차이를 비교한 뒤 담당자 체크리스트를 남기는 화면입니다.", terms: [["우선 검토지역", "지원 확정지역이 아니라 현장확인을 먼저 시작할 후보"], ["조건부 배치안", "설치·인력·예산 가능성을 확인하기 전의 계산 비교안"], ["신뢰 표시", "자료 누락과 가정 민감도를 함께 알리는 해석 주의등급"]] },
  simulator: { title: "자원 수를 바꾸는 방법", summary: "지역과 서비스를 고른 뒤 변경량을 움직이세요. +는 추가, −는 감축입니다. 오른쪽에서 변경 전후의 부족 정도를 바로 비교할 수 있습니다.", terms: [["공급수준", "잠재수요 1,000명당 기관·서비스 제공인력·정원 수"], ["탐색기준 대비 계산상 격차", "군 분포의 중앙값 수준까지 계산상 벌어진 자원 격차"], ["탐색기준 대비 부족률", "0%면 탐색기준 이상, 100%면 공급이 없는 상태"]] },
  timeline: { title: "시간에 따른 변화를 보는 방법", summary: "한 번만 바꾸는 자원과 매년 반복되는 증감을 나눠 입력하세요. 주황선은 아무 조치가 없을 때, 초록선은 선택한 계획을 적용했을 때입니다.", terms: [["수요 변화율", "돌봄이 필요할 가능성이 있는 인구가 매년 변하는 비율"], ["공급 변화율", "기존 자원이 자연적으로 늘거나 줄어드는 비율"], ["시나리오", "입력한 조건이 계속된다고 가정한 계산이며 미래 확정값은 아님"]] },
  sensitivity: { title: "결과가 얼마나 흔들리는지 확인하세요", summary: "탐색기준·수요·예산 같은 가정을 바꿔도 비슷한 지역이 계속 상위에 남는지 확인하는 화면입니다. 일치율이 높을수록 결과가 비교적 안정적입니다.", terms: [["기준안(BASE)", "현재 설정한 기본 조건"], ["상위 10 일치율", "기준안과 비교안에 공통으로 포함된 지역의 비율"], ["순위상관", "1에 가까울수록 두 조건의 지역 순서가 비슷함"]] },
  access: { title: "주변 지역의 도움까지 포함해 보세요", summary: "우리 군 안의 자원만 보지 않고, 같은 도의 남는 자원에 접근할 수 있다고 가정했을 때 부족이 얼마나 줄어드는지 보여줍니다.", terms: [["접근 가능한 공급", "다른 지역에 있지만 계산상 이용할 수 있다고 본 자원"], ["완충효과", "주변 지역 자원을 반영해 줄어든 공급부족"], ["간접 영향", "한 지역의 자원변경이 주변 지역 계산에도 미치는 변화"]] },
  reports: { title: "결과와 근거를 함께 내려받으세요", summary: "선택 지역의 진단 결과는 CSV로 내려받고, 인쇄 화면에서는 PDF로 저장할 수 있습니다. 자료 기준일과 해석 주의사항도 보고서에 포함됩니다.", terms: [["CSV", "표 계산과 추가 분석에 적합한 데이터 파일"], ["PDF", "브라우저 인쇄 메뉴에서 PDF로 저장하는 한 장 보고서"], ["품질 경고", "기준일 차이·비공개·접근성 가정을 알려주는 주의사항"]] },
};

export const resourceLabel = (value: string) => value === "핵심인력" ? "서비스 제공인력" : value;

export const VULNERABILITY_COMPONENTS = [
  { key: "aging_rate", zKey: "z_aging_rate", label: "고령화율", weight: 0.2, description: "전체 인구 중 65세 이상 인구 비율", format: (value: number) => `${fmt(value)}%` },
  { key: "age_85_rate", zKey: "z_age_85_rate", label: "85세 이상 비율", weight: 0.2, description: "전체 인구 중 85세 이상 인구 비율", format: (value: number) => `${fmt(value)}%` },
  { key: "elderly_single_household_burden", zKey: "z_elderly_single_household_burden", label: "고령 1인세대 부담", weight: 0.2, description: "65세 이상 인구 100명당 고령 1인세대 수", format: (value: number) => `${fmt(value)}명` },
  { key: "ltci_recognition_rate", zKey: "z_ltci_recognition_rate", label: "장기요양 인정자 비율", weight: 0.25, description: "65세 이상 인구 중 장기요양 인정자 비율", format: (value: number) => `${fmt(value)}%` },
  { key: "ltci_demand_growth", zKey: "z_ltci_demand_growth", label: "장기요양 수요 증가율", weight: 0.15, description: "분석기간의 장기요양 인정수요 증가 정도", format: (value: number) => `${fmt(value * 100)}%` },
] as const;
