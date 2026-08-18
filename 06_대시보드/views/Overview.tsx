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
        <h2 id="portfolio-title">같은 5개의 방문간호기관, 무엇을 우선해 어디에 배치해야 할까?</h2>
        <p>
          76개 농촌 군의 장기요양 수요·기관·인력·정원을 결합해, 동일한 방문간호기관 5개소를 수요·공급격차·기관 미관측·지역취약성 기준으로 배치했을 때 결과가 어떻게 달라지는지 비교했습니다.
        </p>
        <div className="hero-badges">
          <span>76개 군</span><span>3개 재가서비스</span>
          <span>7개 공급축</span><span>2026.05–06</span>
        </div>
        <div className="hero-actions" aria-label="프로젝트 바로가기">
          <button onClick={onCompareAllocation}>배치전략 비교하기</button>
          <button onClick={onOpenWhatIf}>지역별 What-if 체험</button>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">GitHub</a>
          <a href={CASE_STUDY_URL} target="_blank" rel="noreferrer">Case Study</a>
        </div>
      </div>
    </section>
  );
}
