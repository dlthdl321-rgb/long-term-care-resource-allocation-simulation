const GITHUB_URL =
  "https://github.com/dlthdl321-rgb/long-term-care-resource-allocation-simulation";
const CASE_STUDY_URL = `${GITHUB_URL}/blob/main/CASE_STUDY.md`;

export function OverviewHero({
  onCompareAllocation,
  onOpenWhatIf,
}: {
  onCompareAllocation: () => void;
  onOpenWhatIf: () => void;
}) {
  return (
    <section className="portfolio-hero" aria-labelledby="portfolio-title">
      <div className="hero-copy">
        <p className="hero-label">PUBLIC DATA · ANALYTICS PORTFOLIO</p>
        <h2 id="portfolio-title">한정된 장기요양 자원, 무엇을 우선해 어디에 배치해야 할까?</h2>
        <p>
          지역별 장기요양 인정자 기반 잠재수요와 기관·서비스 제공인력·정원을 결합해 공급격차를 진단하고, 동일한 자원을 서로 다른 기준으로 배치했을 때 결과가 어떻게 달라지는지 비교했습니다.
        </p>
        <div className="hero-badges">
          <span>76개 군</span><span>3개 재가서비스</span>
          <span>7개 공급축</span><span>2026.05–06</span>
        </div>
        <div className="hero-actions" aria-label="프로젝트 바로가기">
          <button onClick={onCompareAllocation}>대표 5개소·4개 전략 비교하기</button>
          <button onClick={onOpenWhatIf}>조건을 바꿔보는 What-if 분석</button>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">GitHub</a>
          <a href={CASE_STUDY_URL} target="_blank" rel="noreferrer">Case Study</a>
        </div>
      </div>
    </section>
  );
}
