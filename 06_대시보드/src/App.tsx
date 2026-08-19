import { useEffect, useMemo, useState } from "react";
import { InsightCallout } from "./components/InsightCallout";
import { MetricBar as Bar } from "./components/MetricBar";
import { TimelineChart } from "./components/TimelineChart";
import { calculateAllocations } from "./lib/allocation";
import {
  DASHBOARD_DATASETS,
  DEFERRED_DASHBOARD_DATASETS,
  downloadCsv,
  loadDashboardJson,
} from "./lib/data";
import { fmt, formatResourceAmount, numberOrZero, parseNumber, pct, requireNumber, resourceUnit } from "./lib/format";
import { buildTimelineScenario } from "./lib/timeline";
import type {
  BaselineRow,
  DashboardRow as Row,
  QualityRow,
  RegionRow,
  ResourceType,
  ServiceType,
  TimelinePoint,
} from "./types";
import { OverviewHero } from "./views/Overview";
import { resourceLabel, VIEW_GUIDES, VULNERABILITY_COMPONENTS, type View } from "./dashboard-config";
import {
  actionGuidance,
  comparePreset,
  FIELD_SCENARIOS,
  fieldSummary,
  reliabilityLabel,
  targetTiers,
} from "./lib/field-support";

const EMPTY_ROWS: Row[] = [];
const REPRESENTATIVE_WHATIF = {
  regionCode: "48890",
  regionName: "합천군",
  service: "방문간호",
  resource: "기관",
  delta: 1,
} as const;
const GITHUB_URL =
  "https://github.com/dlthdl321-rgb/long-term-care-resource-allocation-simulation";
const CASE_STUDY_URL = `${GITHUB_URL}/blob/main/CASE_STUDY.md`;

export default function Home() {
  const [view, setView] = useState<View>("overview");
  const [data, setData] = useState<Record<string, Row[]>>({});
  const [error, setError] = useState("");
  const [province, setProvince] = useState("전체");
  const [regionSort, setRegionSort] = useState("urgency");
  const [service, setService] = useState<ServiceType>("방문간호");
  const [resource, setResource] = useState<ResourceType>("기관");
  const [selectedRegion, setSelectedRegion] = useState("48890");
  const [delta, setDelta] = useState(1);
  const [timelineDelta, setTimelineDelta] = useState(1);
  const [annualAddition, setAnnualAddition] = useState(0);
  const [demandGrowth, setDemandGrowth] = useState(3);
  const [demandAcceleration, setDemandAcceleration] = useState(0.5);
  const [supplyGrowth, setSupplyGrowth] = useState(0);
  const [horizon, setHorizon] = useState(5);
  const [allocationBudget, setAllocationBudget] = useState(5);
  const [allocationCap, setAllocationCap] = useState(2);
  const [fieldChecks, setFieldChecks] = useState<Record<string, boolean>>({});

  useEffect(() => {
    Promise.all(
      DASHBOARD_DATASETS.map(
        async (name) => [name, await loadDashboardJson(name)] as const,
      ),
    )
      .then((entries) => setData(Object.fromEntries(entries)))
      .catch((reason) => setError(String(reason)));
  }, []);
  useEffect(() => {
    if (view !== "access" || data["access-contributions"]) return;
    Promise.all(
      DEFERRED_DASHBOARD_DATASETS.map(
        async (name) => [name, await loadDashboardJson(name)] as const,
      ),
    )
      .then((entries) =>
        setData((current) => ({ ...current, ...Object.fromEntries(entries) })),
      )
      .catch((reason) => setError(String(reason)));
  }, [view, data]);

  const regions = (data.regions ?? EMPTY_ROWS) as RegionRow[];
  const baseline = (data.baseline ?? EMPTY_ROWS) as BaselineRow[];
  const stability = data.stability ?? EMPTY_ROWS;
  const accessRegions = data["access-regions"] ?? EMPTY_ROWS;
  const accessMetrics = data["access-metrics"] ?? EMPTY_ROWS;
  const impact = data["access-impact"] ?? EMPTY_ROWS;
  const supplyTrends = data["supply-trends"] ?? EMPTY_ROWS;
  const workforce = data.workforce ?? EMPTY_ROWS;
  const history = data.history ?? EMPTY_ROWS;
  const accessContributions = data["access-contributions"] ?? EMPTY_ROWS;
  const quality = (data.quality ?? EMPTY_ROWS) as QualityRow[];
  const portfolioSummary = data["portfolio-summary"]?.[0];
  const provinces = useMemo(
    () => ["전체", ...Array.from(new Set(regions.map((r) => r.sido_name))).sort()],
    [regions],
  );
  const visibleRegions = useMemo(
    () =>
      regions.filter((r) => province === "전체" || r.sido_name === province),
    [regions, province],
  );
  useEffect(() => {
    if (
      visibleRegions.length > 0 &&
      !visibleRegions.some((row) => row.region_code === selectedRegion)
    ) {
      setSelectedRegion(visibleRegions[0].region_code);
    }
  }, [visibleRegions, selectedRegion]);
  const topUrgency = [...visibleRegions]
    .sort((a, b) => numberOrZero(a.urgency_rank) - numberOrZero(b.urgency_rank))
    .slice(0, 10);
  const regionSortKeys: Record<string, string> = {
    urgency: "urgency_score", shortage: "supply_shortage_score",
    demand: "demand_pressure_score", vulnerability: "vulnerability_percentile",
  };
  const sortedRegions = [...visibleRegions].sort(
    (a, b) => numberOrZero(b[regionSortKeys[regionSort]]) - numberOrZero(a[regionSortKeys[regionSort]]),
  );
  const regionSortMax = Math.max(
    ...visibleRegions.map((row) => numberOrZero(row[regionSortKeys[regionSort]])),
    1,
  );
  const providerMissingCount = (serviceName: string) =>
    baseline.filter(
      (row) => row.service === serviceName && row.resource_type === "기관" && row.provider_missing === "True",
    ).length;
  const relievedRegions = accessRegions.filter(
    (r) => numberOrZero(r.total_access_relief) > 0,
  ).length;
  const startDemo = () => {
    setSelectedRegion(REPRESENTATIVE_WHATIF.regionCode);
    setService(REPRESENTATIVE_WHATIF.service);
    setResource(REPRESENTATIVE_WHATIF.resource);
    setDelta(REPRESENTATIVE_WHATIF.delta);
    setView("simulator");
    window.history.replaceState(null, "", "#demo");
  };
  const startAllocationComparison = () => {
    setService("방문간호");
    setResource("기관");
    setAllocationBudget(5);
    setAllocationCap(2);
    setView("sensitivity");
    window.history.replaceState(null, "", "#allocation");
  };

  const selected = baseline.find(
    (r) =>
      r.region_code === selectedRegion &&
      r.service === service &&
      r.resource_type === resource,
  );
  const selectedCurrent = selected
    ? requireNumber(selected.current_resource, "current_resource")
    : 0;
  const selectedDemand = selected
    ? requireNumber(selected.demand_value, "demand_value")
    : null;
  if (selectedDemand !== null && selectedDemand <= 0) {
    throw new Error("demand_value는 양수여야 합니다.");
  }
  const selectedTarget = selected
    ? requireNumber(selected.target_resource, "target_resource")
    : null;
  const selectedTargetSupply = selected
    ? requireNumber(selected.target_supply_level, "target_supply_level")
    : null;
  const afterResource = Math.max(0, selectedCurrent + delta);
  const afterSupply = selected
    ? (afterResource / selectedDemand!) * 1000
    : 0;
  const afterGap = selected
    ? Math.max(0, selectedTarget! - afterResource)
    : 0;
  const afterShortage =
    selected && selectedTargetSupply! > 0
      ? 1 - Math.min(1, afterSupply / selectedTargetSupply!)
      : 0;
  const selectedRegionName = regions.find(
    (r) => r.region_code === selectedRegion,
  );
  const selectedTrend = supplyTrends.find(
    (r) =>
      r.region_code === selectedRegion &&
      r.service === service &&
      r.resource_type === resource,
  );
  const provider = baseline.find(
    (r) =>
      r.region_code === selectedRegion &&
      r.service === service &&
      r.resource_type === "기관",
  );
  const providerResource = parseNumber(provider?.current_resource);
  const structuralWarning =
    delta > 0 &&
    resource !== "기관" &&
    providerResource !== null &&
    providerResource <= 0;
  const regionInventory = baseline
    .filter((row) => row.region_code === selectedRegion)
    .sort((a, b) => {
      const serviceOrder = ["방문요양", "방문간호", "주야간보호"];
      const resourceOrder = ["기관", "핵심인력", "정원"];
      return (
        serviceOrder.indexOf(a.service) - serviceOrder.indexOf(b.service) ||
        resourceOrder.indexOf(a.resource_type) -
          resourceOrder.indexOf(b.resource_type)
      );
    });
  const selectedWorkforce = workforce.filter(
    (row) => row.region_code === selectedRegion,
  );
  const selectedHistory = history
    .filter((row) => row.region_code === selectedRegion)
    .sort((a, b) => numberOrZero(a.year) - numberOrZero(b.year));
  const selectedContributions = accessContributions
    .filter(
      (row) =>
        row.origin_region_code === selectedRegion &&
        numberOrZero(row.weighted_external_resource) > 0,
    )
    .sort(
      (a, b) =>
        numberOrZero(b.weighted_external_resource) -
        numberOrZero(a.weighted_external_resource),
    );
  const contributionRegionName = (code: string) =>
    regions.find((row) => row.region_code === code)?.sigungu_name || code;
  const selectedAccess = accessRegions.find(
    (row) => row.region_code === selectedRegion,
  );
  const selectedAccessRelief = numberOrZero(selectedAccess?.total_access_relief);
  const fieldConclusions = fieldSummary(
    selectedRegionName,
    selected,
    selectedAccessRelief,
  );
  const fieldActions = actionGuidance(
    selected,
    provider,
    selectedAccessRelief,
  );
  const fieldTargetTiers = targetTiers(baseline, selected);
  const fieldReliability = reliabilityLabel(
    selected,
    stability.every((row) => numberOrZero(row.top10_urgency_jaccard) >= 0.5),
  );
  const fieldScenarioRows = FIELD_SCENARIOS.map((scenario) => {
    const scenarioService = scenario.service || service;
    const scenarioResource = scenario.resource || resource;
    const row = baseline.find(
      (item) =>
        item.region_code === selectedRegion &&
        item.service === scenarioService &&
        item.resource_type === scenarioResource,
    );
    return {
      ...scenario,
      service: scenarioService,
      resource: scenarioResource,
      row,
      result: comparePreset(row, scenario.delta),
    };
  }).filter((scenario) => scenario.row && scenario.result);
  const fieldChecklist = [
    "현재 자원값과 자료 기준일을 확인했다",
    "기관과 서비스 제공인력을 구분해 확인했다",
    "외부공급은 실제 이동 가능성이 아닌 계산 가정임을 확인했다",
    "탐색기준을 바꿨을 때 결과가 달라지는지 확인했다",
    "개선지역과 악화지역을 모두 확인했다",
    "계산 부족량을 공식 필요량으로 표현하지 않았다",
    "최종 결정 전 담당부서 검토가 필요함을 기록했다",
  ];

  const automaticAllocations = useMemo(() => calculateAllocations({
    budget: allocationBudget,
    capPerRegion: allocationCap,
    baselineRows: baseline,
    regionRows: regions,
    visibleRegionRows: visibleRegions,
    service,
    resourceType: resource,
  }), [
    allocationBudget,
    allocationCap,
    baseline,
    regions,
    resource,
    service,
    visibleRegions,
  ]);

  const observedDemandAnnual =
    selectedRegionName && numberOrZero(selectedRegionName.ltci_demand_growth) > -1
      ? (Math.pow(1 + numberOrZero(selectedRegionName.ltci_demand_growth), 1 / 3) - 1) *
        100
      : 0;
  const observedSupplyAnnual = numberOrZero(selectedTrend?.annual_supply_growth) * 100;
  const timeline = useMemo<TimelinePoint[]>(() => buildTimelineScenario({
    baseline: selected,
    horizon,
    demandGrowth,
    demandAcceleration,
    supplyGrowth,
    initialResourceChange: timelineDelta,
    annualResourceChange: annualAddition,
  }), [
    selected,
    horizon,
    demandGrowth,
    demandAcceleration,
    supplyGrowth,
    timelineDelta,
    annualAddition,
  ]);
  const cumulativeGapAvoided = timeline.reduce(
    (sum, row) => sum + row.baselineGap - row.scenarioGap,
    0,
  );
  const targetYear = timeline.find((row) => row.scenarioGap <= 1e-9)?.year;
  const finalTimeline = timeline[timeline.length - 1];
  const finalGapImprovement =
    (finalTimeline?.baselineGap || 0) - (finalTimeline?.scenarioGap || 0);
  const finalShortageImprovement =
    (finalTimeline?.baselineShortage || 0) -
    (finalTimeline?.scenarioShortage || 0);

  const directImpacts = impact.filter((r) => r.impact_scope === "직접");
  const indirectImpacts = impact.filter((r) => r.impact_scope === "간접");

  const nav: { id: View; label: string; eyebrow: string; group: string }[] = [
    { id: "overview", label: "한눈에 보기", eyebrow: "01", group: "OVERVIEW" },
    { id: "regions", label: "지역별 비교", eyebrow: "02", group: "DIAGNOSE" },
    { id: "diagnosis", label: "한 장 진단서", eyebrow: "03", group: "DIAGNOSE" },
    { id: "field", label: "현장 검토", eyebrow: "04", group: "DIAGNOSE" },
    { id: "simulator", label: "자원 변경", eyebrow: "05", group: "SIMULATE" },
    { id: "timeline", label: "과거·미래 변화", eyebrow: "06", group: "SIMULATE" },
    { id: "sensitivity", label: "자동 배치", eyebrow: "07", group: "SIMULATE" },
    { id: "access", label: "외부공급", eyebrow: "08", group: "SIMULATE" },
    { id: "reports", label: "보고서·품질", eyebrow: "09", group: "EVIDENCE" },
  ];
  const guide = VIEW_GUIDES[view];

  if (error) return <main className="error-state">{error}</main>;
  if (!regions.length)
    return (
      <main className="loading-state">
        <span className="pulse" />
        실데이터를 불러오는 중입니다
      </main>
    );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">LTC</span>
          <div>
            <strong>돌봄자원 랩</strong>
            <small>76개 군 시뮬레이션</small>
          </div>
        </div>
        <nav aria-label="대시보드 화면">
          {nav.map((item, index) => (
            <div className="nav-entry" key={item.id}>
              {(index === 0 || nav[index - 1].group !== item.group) && (
                <small className="nav-group">{item.group}</small>
              )}
              <button
                className={view === item.id ? "nav-item active" : "nav-item"}
                onClick={() => setView(item.id)}
              >
                <span>{item.eyebrow}</span>
                {item.label}
              </button>
            </div>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />
          2026년 5–6월 자료
          <small>탐색기준 · 정책 확정값 아님</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="kicker">LONG-TERM CARE RESOURCE ALLOCATION</p>
            <h1>{nav.find((item) => item.id === view)?.label}</h1>
          </div>
          <label className="province-control">
            <span>분석 범위</span>
            <select value={province} onChange={(e) => setProvince(e.target.value)}>
              {provinces.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
        </header>
        {view === "overview" && (
          <OverviewHero
            onCompareAllocation={startAllocationComparison}
            onOpenWhatIf={startDemo}
          />
        )}

        {view !== "overview" && <details className="plain-guide" aria-label="화면 설명과 핵심 용어">
          <summary>
            <span>화면 읽는 법</span>
            <strong>{guide.title}</strong>
            <small>용어와 해석 주의사항 펼치기</small>
          </summary>
          <div className="guide-details">
            <div className="guide-copy">
              <p>{guide.summary}</p>
            </div>
            <dl>
              {guide.terms.map(([term, meaning]) => (
                <div key={term}>
                  <dt>{term}</dt>
                  <dd>{meaning}</dd>
                </div>
              ))}
            </dl>
          </div>
        </details>}

        {view === "overview" && (
          <>
            <section className="demo-section" aria-labelledby="demo-title">
              <div>
                <span>대표 시나리오 · 방문간호기관 5개소</span>
                <h2 id="demo-title">같은 5개 방문간호기관, 우선하는 목표에 따라 배치지역이 달랐습니다.</h2>
                <div className="strategy-example-grid">
                  <p><small>많은 잠재수요 고려</small><strong>수요규모 우선</strong><span>배치 대상지역 잠재수요 합계 {fmt(numberOrZero(portfolioSummary?.demand_proportional_benefited_demand), 0)}명</span></p>
                  <p><small>기관 공백 완화</small><strong>기관 미관측 우선</strong><span>기관 미관측 상태 {portfolioSummary?.zero_provider_regions_reduced}곳 해소(계산상)</span></p>
                  <p><small>공급격차 완화</small><strong>공급부족량 우선</strong><span>방문간호·기관 분석축에서 격차가 큰 지역부터 배치</span></p>
                  <p><small>취약지역 고려</small><strong>지역취약성 우선</strong><span>배치용 취약성 점수가 높은 지역부터 배치(고령화율 50% + 고령 1인세대 부담 50%)</span></p>
                </div>
                <p><strong>단일 우승 전략을 선언하기보다, 무엇을 정책목표로 두느냐에 따라 배치안을 비교할 필요가 있었습니다.</strong></p>
              </div>
              <button onClick={startAllocationComparison}>배치전략 직접 비교하기 →</button>
            </section>
            <section id="key-findings" className="finding-section">
              <div className="portfolio-section-head">
                <span>KEY FINDINGS</span>
                <h2>전략 비교를 뒷받침하는 두 가지 근거</h2>
                <p>공개자료의 미관측 범위와 단일 지표의 한계를 확인했습니다.</p>
              </div>
              <div className="finding-grid">
                <article>
                  <b>01 · 공급기반 공백</b>
                  <strong>76개 군 중 {providerMissingCount("방문간호")}곳에서 방문간호기관이 공개자료상 확인되지 않았습니다.</strong>
                  <p>주야간보호기관 {providerMissingCount("주야간보호")}곳 · 방문요양기관 {providerMissingCount("방문요양")}곳</p>
                  <small>기관 미관측은 공개자료에서 기관이 확인되지 않았다는 뜻이며 실제 기관 부재를 확정하지 않습니다.</small>
                  <a href={`${CASE_STUDY_URL}#5-key-findings`} target="_blank" rel="noreferrer">근거 보기 →</a>
                </article>
                <article>
                  <b>02 · 지표 설계 판단</b>
                  <strong>고령화만으로 공급부족 지역을 설명하기 어려웠습니다.</strong>
                  <p>
                    고령화율만으로 서비스 공급병목을 충분히 설명하기 어려워 수요·기관·인력·정원·공급기반 공백을 함께 고려했습니다.
                  </p>
                  <a href={`${GITHUB_URL}/blob/main/03_데이터/outputs/hypothesis_testing/q1_vulnerability_supply_spearman.csv`} target="_blank" rel="noreferrer">분석 근거 보기 →</a>
                </article>
              </div>
            </section>
            <section className="built-section" aria-labelledby="built-title">
              <div className="portfolio-section-head">
                <span>WHAT I BUILT</span>
                <h2 id="built-title">현황판이 아닌 의사결정 지원 도구</h2>
              </div>
              <div className="finding-grid">
                <article><b>지역 병목 진단</b><p>서비스별 수요와 기관·인력·정원을 분리해 상대 공급격차를 확인합니다.</p></article>
                <article><b>What-if 자원 변경</b><p>자원을 증감하고 탐색기준 대비 Before/After를 비교합니다.</p></article>
                <article><b>자동 자원배치</b><p>같은 총량에서 서로 다른 배치 기준의 결과를 비교합니다.</p></article>
                <article><b>검증 및 민감도 분석</b><p>수요·탐색기준·예산을 바꿔도 결과가 얼마나 유지되는지 점검합니다.</p></article>
              </div>
            </section>
            <section id="analysis-process" className="process-section">
              <div className="portfolio-section-head">
                <span>ANALYSIS PROCESS</span>
                <h2>원자료에서 의사결정 화면까지</h2>
                <p>각 단계의 처리와 분석 판단, 산출물을 함께 남겼습니다.</p>
              </div>
              <ol className="process-flow">
                <li>
                  <b>01</b><strong>공공데이터 수집</strong>
                  <p>인구·인정자·기관·인력·정원 자료의 시점과 공개범위를 확인</p>
                  <small>산출물 · 원자료 및 출처 기록</small>
                </li>
                <li>
                  <b>02</b><strong>단위 표준화·검증</strong>
                  <p>지역코드와 서비스 분류를 맞추고 결측·중복·결합범위를 감사</p>
                  <small>판단 · 미확인과 실제 0을 구분</small>
                </li>
                <li>
                  <b>03</b><strong>수요·공급지표 생성</strong>
                  <p>인정자 1,000명당 기관·인력·정원을 서로 합산하지 않고 계산</p>
                  <small>산출물 · 532개 기준선 조합</small>
                </li>
                <li>
                  <b>04</b><strong>통계 진단</strong>
                  <p>기술통계와 연관성 분석으로 단일 취약성 지표의 한계를 확인</p>
                  <small>판단 · 상관을 인과로 해석하지 않음</small>
                </li>
                <li>
                  <b>05</b><strong>배치전략 비교</strong>
                  <p>같은 총량·탐색기준·상한에서 수요·격차·공백·취약성 전략을 비교</p>
                  <small>산출물 · 전략별 전후 성과표</small>
                </li>
                <li>
                  <b>06</b><strong>민감도·한계 검토</strong>
                  <p>탐색기준·수요·예산 조건을 바꾸고 계산 결과의 안정성을 점검</p>
                  <small>한계 · 실제 이동시간과 운영가능성은 현장검증 필요</small>
                </li>
              </ol>
            </section>
            <details className="plain-guide overview-guide" aria-label="분석 기준과 핵심 용어">
              <summary><span>분석 기준·용어</span><strong>탐색결과를 해석하기 전에 확인하세요</strong><small>용어와 해석 주의사항 펼치기</small></summary>
              <div className="guide-details"><div className="guide-copy"><p>{guide.summary}</p></div><dl>{guide.terms.map(([term, meaning]) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl></div>
            </details>
            <section className="about-section" aria-labelledby="about-title">
              <div>
                <span>ABOUT THE PROJECT</span>
                <h2 id="about-title">분석가의 판단이 보이는 프로젝트</h2>
                <p>
                  공급량을 하나로 뭉치지 않고 기관·서비스 제공인력·정원을
                  분리했으며, 단일 순위 대신 정책목표가 다른 배치전략을
                  동일 조건에서 비교했습니다. 결과는 설치 확정안이 아니라
                  현장검토 후보를 좁히는 탐색 근거입니다.
                </p>
              </div>
              <dl>
                <div>
                  <dt>확인된 구현 범위</dt>
                  <dd>수집·전처리·통계분석·시뮬레이션·대시보드·검증</dd>
                </div>
                <div>
                  <dt>기술</dt>
                  <dd>Python · pandas · NumPy · SciPy · Matplotlib · TypeScript · React</dd>
                </div>
                <div>
                  <dt>핵심 한계</dt>
                  <dd>공개 집계자료 기반 계산이며 정책 인과효과를 증명하지 않음</dd>
                </div>
              </dl>
            </section>
          </>
        )}

        {view === "regions" && (
          <section className="panel">
            <div className="section-head">
              <div>
                <span className="section-index">02</span>
                <h2>어느 지역부터 살펴봐야 할까요?</h2>
              </div>
              <small>행을 선택하면 자원 변경 화면으로 이어집니다</small>
            </div>
            <InsightCallout
              title={`${topUrgency[0]?.sigungu_name || "상위 지역"}부터 현장확인 근거를 살펴보세요.`}
              detail="탐색용 검토 순서는 지원 확정순위가 아닙니다. 분석 목적에 따라 정렬 기준을 바꿔 후보지역이 달라지는지 확인하세요."
            />
            <label className="province-control region-sort-control">
              <span>정렬 기준</span>
              <select value={regionSort} onChange={(e) => setRegionSort(e.target.value)}>
                <option value="urgency">종합 탐색용 검토 순서</option>
                <option value="shortage">공급격차</option>
                <option value="demand">수요부담</option>
                <option value="vulnerability">종합 지역취약성 탐색점수</option>
              </select>
            </label>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>탐색용 순서</th>
                    <th>지역</th>
                    <th>고령화율</th>
                    <th>돌봄수요 부담</th>
                    <th>자원부족 점수</th>
                    <th>가장 부족한 자원</th>
                    <th>선택 지표 점수</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRegions
                    .map((row) => (
                      <tr
                        key={row.region_code}
                        onClick={() => {
                          setSelectedRegion(row.region_code);
                          setService(row.top_shortage_service);
                          setResource(row.top_shortage_resource_type);
                          setView("diagnosis");
                        }}
                      >
                        <td className="rank-cell">{sortedRegions.indexOf(row) + 1}</td>
                        <td>
                          <strong>{row.sigungu_name}</strong>
                          <small>{row.sido_name}</small>
                        </td>
                        <td>{fmt(numberOrZero(row.aging_rate))}%</td>
                        <td>{fmt(numberOrZero(row.demand_pressure_score))}</td>
                        <td>{fmt(numberOrZero(row.supply_shortage_score))}</td>
                        <td>
                          {row.top_shortage_service} ·{" "}
                          {resourceLabel(row.top_shortage_resource_type)}
                        </td>
                        <td className="urgency-cell">
                          <Bar value={numberOrZero(row[regionSortKeys[regionSort]])} max={regionSortMax} />
                          <b>{fmt(numberOrZero(row[regionSortKeys[regionSort]]))}</b>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {view === "diagnosis" && selectedRegionName && (
          <div className="diagnosis-page">
            <section className="diagnosis-hero">
              <div>
                <span className="section-index">진단</span>
                <p>{selectedRegionName.sido_name}</p>
                <h2>{selectedRegionName.sigungu_name} 한 장 진단서</h2>
                <small>
                  인구·수요 2026년 5~6월, 공급 2026년 6월 기준 · 현장확인
                  보조자료
                </small>
              </div>
              <div className="diagnosis-actions">
                <select
                  aria-label="진단 지역"
                  value={selectedRegion}
                  onChange={(event) => setSelectedRegion(event.target.value)}
                >
                  {[...visibleRegions]
                    .sort((a, b) =>
                      a.sigungu_name.localeCompare(b.sigungu_name, "ko"),
                    )
                    .map((row) => (
                      <option value={row.region_code} key={row.region_code}>
                        {row.sido_name} {row.sigungu_name}
                      </option>
                    ))}
                </select>
                <button onClick={() => window.print()}>PDF로 저장</button>
              </div>
            </section>

            <section className="diagnosis-kpis">
              <article>
                <span>고령화율</span>
                <strong>{fmt(numberOrZero(selectedRegionName.aging_rate))}%</strong>
                <small>전체 인구 중 65세 이상 비율</small>
              </article>
              <article>
                <span>85세 이상 비율</span>
                <strong>{fmt(numberOrZero(selectedRegionName.age_85_rate))}%</strong>
                <small>초고령 돌봄수요 참고지표</small>
              </article>
              <article>
                <span>장기요양 잠재수요 추정치</span>
                <strong>{fmt(numberOrZero(selectedRegionName.ltci_demand), 0)}</strong>
                <small>공개자료와 비공개 셀 범위를 반영한 추정 중앙값</small>
              </article>
              <article>
                <span>현장검토 후보 순서</span>
                <strong>{selectedRegionName.urgency_rank}위</strong>
                <small>76개 군 비교 · 배분 확정순위 아님</small>
              </article>
            </section>
            <section className="panel vulnerability-explainer">
              <div className="section-head">
                <div>
                  <span className="section-index">취약성</span>
                  <h2>종합 지역취약성 탐색점수는 어떻게 계산하나요?</h2>
                </div>
                <div className="vulnerability-score-head">
                  <span>종합 취약성 탐색 백분위</span>
                  <strong>
                    {fmt(numberOrZero(selectedRegionName.vulnerability_percentile), 1)}점
                  </strong>
                </div>
              </div>
              <div className="vulnerability-definition">
                <strong>
                  고령인구와 장기요양 부담이 다른 군보다 얼마나 큰지를 5개
                  지표로 비교한 상대점수입니다.
                </strong>
                <p>
                  각 지표를 76개 군 평균이 0이 되도록 표준화한 뒤 아래
                  가중치를 곱해 더합니다. 원점수{" "}
                  <b>{fmt(numberOrZero(selectedRegionName.vulnerability_score), 3)}</b>는
                  양수면 76개 군 평균보다 취약성이 높은 편, 음수면 낮은
                  편이라는 뜻입니다. 금액·인원·필요자원 수가 아닙니다.
                </p>
              </div>
              <div className="vulnerability-components">
                {VULNERABILITY_COMPONENTS.map((component) => {
                  const z = numberOrZero(selectedRegionName[component.zKey]);
                  return (
                    <article key={component.key}>
                      <header>
                        <span>{component.label}</span>
                        <b>가중치 {component.weight * 100}%</b>
                      </header>
                      <strong>
                        {component.format(numberOrZero(selectedRegionName[component.key]))}
                      </strong>
                      <small>{component.description}</small>
                      <div className={z >= 0 ? "above" : "below"}>
                        76개 군 평균보다{" "}
                        {z >= 0
                          ? `${fmt(Math.abs(z), 2)} 표준편차 높음`
                          : `${fmt(Math.abs(z), 2)} 표준편차 낮음`}
                      </div>
                    </article>
                  );
                })}
              </div>
              <div className="score-flow">
                <p>
                  <span>① 원자료</span>
                  고령화·85세 이상·1인세대·인정자·수요증가
                </p>
                <i>→</i>
                <p>
                  <span>② 표준화</span>
                  76개 군 평균과 비교
                </p>
                <i>→</i>
                <p>
                  <span>③ 가중합</span>
                  지역취약성 원점수
                </p>
                <i>→</i>
                <p>
                  <span>④ 백분위</span>
                  0~100 상대 위치
                </p>
              </div>
              <details className="score-caution">
                <summary>지역취약성 점수와 종합 탐색점수의 차이</summary>
                <p>
                  종합 지역취약성 탐색점수는 인구·가구·장기요양 특성을 함께 봅니다. 종합 탐색점수는 종합 지역취약성 탐색 백분위 30%, 장기요양 수요압력 25%,
                  자원부족 35%, 기관 미관측 등 공급기반 공백 10%를 합친 별도
                  점수입니다. 따라서 종합 지역취약성이 높아도 공급이 충분하면 탐색용 검토 순서는 낮아질 수 있고, 취약성이 상대적으로 낮아도
                  기관 미관측 또는 자원부족이 크면 탐색용 검토 순서는 높아질 수
                  있습니다.
                </p>
              </details>
              <p className="footnote">
                가중치는 공식 정책값이 아니라 현재 기본 시나리오의 탐색
                입력값입니다. 점수만으로 지원 여부나 예산을 결정하지 않고
                개별 지표와 공급부족을 함께 확인해야 합니다.
              </p>
            </section>
            <section className="target-definition">
              <strong>탐색기준 이상은 무엇을 뜻하나요?</strong>
              <p>
                각 서비스·자원별로 76개 군의 잠재수요 1,000명당 공급수준
                중앙값을 탐색기준으로 고정합니다. 지역의 현재 공급수준이 이
                중앙값 이상이면 ‘탐색기준 이상’, 낮으면 ‘탐색기준 미만’입니다. 기관,
                서비스 제공인력, 정원은 단위가 달라 각각 별도로 판단합니다.
                이 기준은 법정 배치기준이나 실제 필요량의 확정값이 아닙니다.
              </p>
            </section>
            <InsightCallout
              title={`${selectedRegionName.top_shortage_service} ${resourceLabel(selectedRegionName.top_shortage_resource_type)}이 상대적으로 가장 부족합니다.`}
              detail={`현재 현장검토 후보 순서는 76개 군 중 ${selectedRegionName.urgency_rank}번째입니다. 아래 표에서는 이 항목의 현재 수와 부족률부터 확인하세요.`}
            />

            <div className="diagnosis-grid">
              <section className="panel">
                <div className="section-head">
                  <div>
                    <span className="section-index">자원</span>
                    <h2>서비스별 현재 자원과 부족률</h2>
                  </div>
                  <small>2026-06-10 공급자료</small>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>서비스</th>
                        <th>자원</th>
                        <th>현재 수</th>
                        <th>탐색기준 대비 부족률</th>
                        <th>상태</th>
                      </tr>
                    </thead>
                    <tbody>
                      {regionInventory.map((row) => (
                        <tr
                          key={`${row.service}-${row.resource_type}`}
                          onClick={() => {
                            setService(row.service);
                            setResource(row.resource_type);
                            setView("simulator");
                          }}
                        >
                          <td>{row.service}</td>
                          <td>{resourceLabel(row.resource_type)}</td>
                          <td className="inventory-number">
                            {fmt(numberOrZero(row.current_resource), 0)}
                          </td>
                          <td>{pct(numberOrZero(row.relative_shortage_score))}</td>
                          <td>{row.resource_state}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="panel">
                <div className="section-head">
                  <div>
                    <span className="section-index">인력</span>
                    <h2>직종별 서비스 제공인력</h2>
                  </div>
                  <small>분석용 합계와 원자료 직종을 분리</small>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>서비스</th>
                        <th>사회복지사</th>
                        <th>간호사</th>
                        <th>간호조무사</th>
                        <th>요양보호사</th>
                        <th>물리·작업치료사</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedWorkforce.map((row) => (
                        <tr key={row.service}>
                          <td>
                            <strong>{row.service}</strong>
                          </td>
                          <td>{fmt(numberOrZero(row.사회복지사), 0)}</td>
                          <td>{fmt(numberOrZero(row.간호사), 0)}</td>
                          <td>{fmt(numberOrZero(row.간호조무사), 0)}</td>
                          <td>{fmt(numberOrZero(row.요양보호사), 0)}</td>
                          <td>
                            {fmt(
                              numberOrZero(row.물리치료사) + numberOrZero(row.작업치료사),
                              0,
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="inventory-note">
                  방문요양·주야간보호 분석용 제공인력은 요양보호사,
                  방문간호는 간호사와 간호조무사 합계입니다. 직종별 수는
                  전일제 환산인력이나 즉시 채용 가능 인력을 뜻하지 않습니다.
                </p>
              </section>
            </div>

            <section className="panel diagnosis-history">
              <div className="section-head">
                <div>
                  <span className="section-index">추이</span>
                  <h2>최근 관측된 인구와 장기요양 수요</h2>
                </div>
                <small>미래 시나리오를 해석하는 과거 근거</small>
              </div>
              <div className="history-cards">
                {selectedHistory.map((row) => (
                  <article key={row.year}>
                    <strong>{row.year}</strong>
                    <span>65세 이상 {fmt(numberOrZero(row.population_65_plus), 0)}명</span>
                    <span>
                      장기요양 인정 공개값{" "}
                      {fmt(numberOrZero(row.ltci_recognized_public), 0)}명
                    </span>
                    <small>
                      고령화율 {fmt(numberOrZero(row.aging_rate))}%
                      {row.suppression_warning ? " · 비공개 셀 주의" : ""}
                    </small>
                  </article>
                ))}
              </div>
              <button
                className="text-action"
                onClick={() => setView("timeline")}
              >
                과거 추이와 미래 시나리오 연결해서 보기 →
              </button>
            </section>
          </div>
        )}

        {view === "field" && selectedRegionName && selected && (
          <div className="field-page">
            <section className="field-summary-card">
              <div className="section-head">
                <div>
                  <span className="section-index">결론</span>
                  <h2>{selectedRegionName.sigungu_name} 실무 검토 요약</h2>
                </div>
                <select
                  aria-label="현장 검토 지역"
                  value={selectedRegion}
                  onChange={(event) => setSelectedRegion(event.target.value)}
                >
                  {[...visibleRegions]
                    .sort((a, b) =>
                      a.sigungu_name.localeCompare(b.sigungu_name, "ko"),
                    )
                    .map((row) => (
                      <option value={row.region_code} key={row.region_code}>
                        {row.sido_name} {row.sigungu_name}
                      </option>
                    ))}
                </select>
              </div>
              <div className="field-conclusions">
                {fieldConclusions.map((sentence, index) => (
                  <p key={sentence}>
                    <b>{index + 1}</b>
                    {sentence}
                  </p>
                ))}
              </div>
              <div className="reliability-row">
                <span
                  className={`reliability-badge ${fieldReliability.level.replaceAll(" ", "")}`}
                >
                  결과 해석: {fieldReliability.level}
                </span>
                <p>{fieldReliability.reason}</p>
              </div>
            </section>

            <div className="field-grid">
              <section className="panel">
                <div className="section-head">
                  <div>
                    <span className="section-index">행동</span>
                    <h2>계산 결과를 무엇으로 검토할까요?</h2>
                  </div>
                  <small>권고가 아닌 담당자 검토문구</small>
                </div>
                <div className="action-guidance-list">
                  {fieldActions.map((item) => (
                    <article className={item.tone} key={item.signal}>
                      <strong>{item.signal}</strong>
                      <p>{item.action}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="section-head">
                  <div>
                    <span className="section-index">기준</span>
                    <h2>탐색기준을 바꾸면 판단이 달라질까요?</h2>
                  </div>
                  <small>법정 기준이 아닌 군 분포 기반 탐색값</small>
                </div>
                <div className="target-tier-list">
                  {fieldTargetTiers.map((tier) => {
                    const met = numberOrZero(selected.current_supply_level) >= tier.value;
                    return (
                      <article key={tier.name}>
                        <span>{tier.name}</span>
                        <strong>{fmt(tier.value, 3)}</strong>
                        <small>{tier.meaning}</small>
                        <b className={met ? "met" : "unmet"}>
                          {met ? "현재 충족" : "현재 미달"}
                        </b>
                      </article>
                    );
                  })}
                </div>
                <p className="inventory-note">
                  현재 선택: {service} {resourceLabel(resource)} · 잠재수요
                  1,000명당 {fmt(numberOrZero(selected.current_supply_level), 3)}
                </p>
              </section>
            </div>

            <section className="panel preset-panel">
              <div className="section-head">
                <div>
                  <span className="section-index">사전안</span>
                  <h2>현장에서 자주 검토할 변경안</h2>
                </div>
                <small>버튼을 누르면 자원 변경 화면에 그대로 적용</small>
              </div>
              <div className="preset-grid">
                {FIELD_SCENARIOS.map((scenario) => (
                  <button
                    key={scenario.label}
                    onClick={() => {
                      if (scenario.service) setService(scenario.service);
                      if (scenario.resource) setResource(scenario.resource);
                      setDelta(scenario.delta);
                      setView("simulator");
                    }}
                  >
                    <strong>{scenario.label}</strong>
                    <span>
                      변경량 {scenario.delta > 0 ? `+${scenario.delta}` : scenario.delta}
                    </span>
                    <small>{scenario.note}</small>
                  </button>
                ))}
              </div>
            </section>

            <section className="panel decision-table-panel">
              <div className="section-head">
                <div>
                  <span className="section-index">비교</span>
                  <h2>사전 시나리오 의사결정표</h2>
                </div>
                <small>같은 지역의 계산상 결과를 한 표에서 비교</small>
              </div>
              <details className="detail-table">
                <summary>시나리오별 상세 수치 펼치기</summary>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>검토안</th>
                      <th>서비스·자원</th>
                      <th>변경 후 수</th>
                      <th>변경 후 부족량</th>
                      <th>부족량 변화</th>
                      <th>변경 후 부족률</th>
                      <th>탐색기준 상태</th>
                      <th>구조적 확인사항</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fieldScenarioRows.map((scenario) => (
                      <tr key={scenario.label}>
                        <td><strong>{scenario.label}</strong></td>
                        <td>
                          {scenario.service} · {resourceLabel(scenario.resource)}
                        </td>
                        <td>{fmt(scenario.result!.after, 0)}</td>
                        <td>{fmt(scenario.result!.gapAfter, 2)}</td>
                        <td
                          className={
                            scenario.result!.gapChange > 0
                              ? "negative"
                              : "positive"
                          }
                        >
                          {scenario.result!.gapChange > 0 ? "+" : ""}
                          {fmt(scenario.result!.gapChange, 2)}
                        </td>
                        <td>{pct(scenario.result!.shortageAfter)}</td>
                        <td>{scenario.result!.stateAfter}</td>
                        <td>{scenario.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              </details>
            </section>

            <section className="panel checklist-panel">
              <div className="section-head">
                <div>
                  <span className="section-index">확인</span>
                  <h2>회의 전 검토 체크리스트</h2>
                </div>
                <strong>
                  {Object.values(fieldChecks).filter(Boolean).length}/
                  {fieldChecklist.length} 확인
                </strong>
              </div>
              <div className="checklist-grid">
                {fieldChecklist.map((item) => (
                  <label key={item}>
                    <input
                      type="checkbox"
                      checked={Boolean(fieldChecks[item])}
                      onChange={(event) =>
                        setFieldChecks((current) => ({
                          ...current,
                          [item]: event.target.checked,
                        }))
                      }
                    />
                    <span>{item}</span>
                  </label>
                ))}
              </div>
              <p className="footnote">
                체크 결과는 현재 브라우저에서 검토를 돕기 위한 표시이며 공식
                결재나 현장확인 완료를 증명하지 않습니다.
              </p>
            </section>
          </div>
        )}

        {view === "simulator" && (
          <>
            {selectedRegion === REPRESENTATIVE_WHATIF.regionCode && service === REPRESENTATIVE_WHATIF.service && resource === REPRESENTATIVE_WHATIF.resource && delta === REPRESENTATIVE_WHATIF.delta && (
              <section className="demo-banner" aria-label="데모 시나리오">
                <b>데모 시나리오</b>
                <span>{REPRESENTATIVE_WHATIF.regionName}의 {REPRESENTATIVE_WHATIF.service} {REPRESENTATIVE_WHATIF.resource} +{REPRESENTATIVE_WHATIF.delta}을 가정했습니다.</span>
              </section>
            )}
            <div className="sim-grid">
              <section className="control-panel">
              <span className="section-index">03</span>
              <h2>자원을 얼마나 바꿀까요?</h2>
              <p>지역·서비스·자원을 고른 뒤 +는 추가, −는 감축으로 설정하세요.</p>
              <label>
                지역
                <select
                  value={selectedRegion}
                  onChange={(e) => setSelectedRegion(e.target.value)}
                >
                  {[...visibleRegions]
                    .sort((a, b) => a.sigungu_name.localeCompare(b.sigungu_name, "ko"))
                    .map((row) => (
                      <option value={row.region_code} key={row.region_code}>
                        {row.sido_name} {row.sigungu_name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                서비스
                <select
                  value={service}
                  onChange={(e) => {
                    const next = e.target.value;
                    setService(next);
                    if (next !== "주야간보호" && resource === "정원") {
                      setResource("기관");
                    }
                  }}
                >
                  <option>방문요양</option>
                  <option>방문간호</option>
                  <option>주야간보호</option>
                </select>
              </label>
              <label>
                바꿀 자원
                <select
                  value={resource}
                  onChange={(e) => setResource(e.target.value)}
                >
                  <option>기관</option>
                  <option value="핵심인력">서비스 제공인력</option>
                  {service === "주야간보호" && <option>정원</option>}
                </select>
              </label>
              <label>
                추가하거나 줄일 수 <strong>{delta > 0 ? `+${delta}` : delta}</strong>
                <input
                  type="range"
                  min={-10}
                  max={20}
                  value={delta}
                  onChange={(e) => setDelta(Number(e.target.value))}
                />
              </label>
              {structuralWarning && (
                <div className="warning">
                  공개자료에서 해당 서비스 기관이 관측되지 않은 지역에는 인력·정원만 단독 추가할 수 없습니다.
                </div>
              )}
              </section>
              <section className="simulation-output">
              <div className="scenario-title">
                <div>
                  <p>{selectedRegionName?.sido_name}</p>
                  <h2>
                    {selectedRegionName?.sigungu_name} · {service}{" "}
                    {resourceLabel(resource)}
                  </h2>
                </div>
                <span>{delta >= 0 ? "추가 시나리오" : "감축 시나리오"}</span>
              </div>
              <InsightCallout
                label="이번 변경의 뜻"
                title={`${resourceLabel(resource)} ${formatResourceAmount(numberOrZero(selected?.current_resource), resource)}를 ${formatResourceAmount(afterResource, resource)}로 바꿉니다.`}
                detail={`탐색기준 대비 계산상 격차는 ${formatResourceAmount(numberOrZero(selected?.continuous_gap), resource, 2)}에서 ${formatResourceAmount(afterGap, resource, 2)}로 ${afterGap <= numberOrZero(selected?.continuous_gap) ? "줄어듭니다" : "늘어납니다"}.`}
              />
              <div className="target-explainer">
                <div>
                  <span>이 화면의 탐색기준</span>
                  <strong>
                    잠재수요 1,000명당{" "}
                    {fmt(numberOrZero(selected?.target_supply_level), 3)}{" "}
                    {resourceLabel(resource)}
                  </strong>
                </div>
                <p>
                  도 소속 76개 군의 {service} {resourceLabel(resource)}{" "}
                  공급수준 중앙값을 탐색 기준으로 사용합니다. 이 지역의 현재
                  수요에 환산한 탐색기준 자원은{" "}
                  <b>{fmt(numberOrZero(selected?.target_resource), 2)}</b>입니다. 법정
                  배치기준이나 정부가 확정한 적정 공급량은 아닙니다.
                </p>
              </div>
              <div className="before-after">
                <article>
                  <span>현재</span>
                  <strong>{formatResourceAmount(numberOrZero(selected?.current_resource), resource)}</strong>
                  <small>잠재수요 1,000명당 {fmt(numberOrZero(selected?.current_supply_level), 2)}</small>
                </article>
                <div className="change-arrow">→</div>
                <article className="after">
                  <span>변경 후</span>
                  <strong>{formatResourceAmount(afterResource, resource)}</strong>
                  <small>잠재수요 1,000명당 {fmt(afterSupply, 2)}</small>
                </article>
              </div>
              <div className="comparison-list">
                <div>
                  <span>탐색기준 대비 계산상 격차</span>
                  <b>{formatResourceAmount(numberOrZero(selected?.continuous_gap), resource, 2)}</b>
                  <i>→</i>
                  <strong>{formatResourceAmount(afterGap, resource, 2)}</strong>
                </div>
                <div>
                  <span>탐색기준 대비 부족률</span>
                  <b>{pct(numberOrZero(selected?.relative_shortage_score))}</b>
                  <i>→</i>
                  <strong>{pct(afterShortage)}</strong>
                </div>
                <div>
                  <span>탐색기준 상태</span>
                  <b>{selected?.resource_state}</b>
                  <i>→</i>
                  <strong>{afterGap <= 1e-9 ? "탐색기준 이상" : "탐색기준 미만"}</strong>
                </div>
              </div>
              <p className="interpretation">
                이 결과는 입력한 자원 수에 따른 계산상 비교입니다. 실제 설치 가능성,
                이용량, 비용이나 건강효과를 뜻하지 않으므로 현장자료와 함께 확인해야 합니다.
              </p>
              <button
                className="timeline-link-button"
                onClick={() => {
                  setTimelineDelta(delta);
                  setAnnualAddition(0);
                  setView("timeline");
                }}
              >
                이 변경을 시간별로 비교하기 →
              </button>
              </section>
            </div>
            <section className="panel inventory-panel">
              <div className="section-head">
                <div>
                  <span className="section-index">보유</span>
                  <h2>{selectedRegionName?.sigungu_name}에 현재 있는 자원</h2>
                </div>
                <small>
                  행을 선택하면 위의 자원 변경 조건도 같은 항목으로 바뀝니다
                </small>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>서비스</th>
                      <th>자원 종류</th>
                      <th>현재 보유 수</th>
                      <th>잠재수요 1,000명당</th>
                      <th>이번 변경</th>
                      <th>변경 후 수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {regionInventory.map((row) => {
                      const isActive =
                        row.service === service &&
                        row.resource_type === resource;
                      const rowDelta = isActive ? delta : 0;
                      const rowAfter = Math.max(
                        0,
                        numberOrZero(row.current_resource) + rowDelta,
                      );
                      return (
                        <tr
                          key={`${row.service}-${row.resource_type}`}
                          className={isActive ? "selected-resource-row" : ""}
                          onClick={() => {
                            setService(row.service);
                            setResource(row.resource_type);
                          }}
                        >
                          <td>
                            <strong>{row.service}</strong>
                          </td>
                          <td>{resourceLabel(row.resource_type)}</td>
                          <td className="inventory-number">
                            {formatResourceAmount(numberOrZero(row.current_resource), row.resource_type)}
                          </td>
                          <td>{fmt(numberOrZero(row.current_supply_level), 2)}</td>
                          <td className={rowDelta < 0 ? "negative" : "positive"}>
                            {isActive
                              ? rowDelta > 0
                                ? `+${rowDelta}`
                                : rowDelta
                              : "—"}
                          </td>
                          <td className="inventory-number">
                            {isActive ? formatResourceAmount(rowAfter, row.resource_type) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="inventory-note">
                ‘현재 보유 수’는 원자료의 최신 기준값입니다. 서비스 제공인력은
                해당 서비스 공급역량을 나타내기 위해 데이터에서 집계한 주요
                종사자 수입니다.
              </p>
            </section>
            <section className="target-definition simulator-access-link">
              <strong>선택 지역 직접효과만 기본 결과로 표시합니다.</strong>
              <p>같은 도 자원공유 가능성을 단순화한 간접영향은 실제 이동시간·방문권역·수용가능성을 반영하지 않습니다.</p>
              <button onClick={() => setView("access")}>탐색적 외부공급 분석 보기 →</button>
            </section>
          </>
        )}

        {view === "timeline" && (
          <>
            <section className="observed-history">
              <div>
                <span>실제 관측</span>
                <h2>{selectedRegionName?.sigungu_name} 2022~2025 변화</h2>
                <p>
                  공개자료에서 확인된 고령인구와 장기요양 인정수요입니다. 아래
                  2026년 이후 값은 이 관측값과 사용자가 정한 변화율을 연결한
                  계산 시나리오입니다.
                </p>
              </div>
              <div className="history-ribbon">
                {selectedHistory.map((row) => (
                  <article key={row.year}>
                    <strong>{row.year}</strong>
                    <span>
                      인정수요 {fmt(numberOrZero(row.ltci_recognized_public), 0)}
                    </span>
                    <small>65세+ {fmt(numberOrZero(row.population_65_plus), 0)}명</small>
                  </article>
                ))}
                <i>→</i>
                <article className="forecast-start">
                  <strong>2026+</strong>
                  <span>사용자 시나리오</span>
                  <small>확정 예측값 아님</small>
                </article>
              </div>
            </section>
            <div className="timeline-layout">
              <section className="control-panel timeline-controls">
                <span className="section-index">04</span>
                <h2>앞으로 어떻게 바뀔까요?</h2>
                <p>
                  수요와 자원이 매년 어떻게 변할지 가정하고, 부족한 양을 연도별로 비교합니다.
                </p>
                <label>
                  지역
                  <select
                    value={selectedRegion}
                    onChange={(e) => setSelectedRegion(e.target.value)}
                  >
                    {[...visibleRegions]
                      .sort((a, b) =>
                        a.sigungu_name.localeCompare(b.sigungu_name, "ko"),
                      )
                      .map((row) => (
                        <option value={row.region_code} key={row.region_code}>
                          {row.sido_name} {row.sigungu_name}
                        </option>
                      ))}
                  </select>
                </label>
                <div className="inline-fields">
                  <label>
                    서비스
                    <select
                      value={service}
                      onChange={(e) => {
                        const next = e.target.value;
                        setService(next);
                        if (next !== "주야간보호" && resource === "정원") {
                          setResource("기관");
                        }
                      }}
                    >
                      <option>방문요양</option>
                      <option>방문간호</option>
                      <option>주야간보호</option>
                    </select>
                  </label>
                  <label>
                    자원
                    <select
                      value={resource}
                      onChange={(e) => setResource(e.target.value)}
                    >
                      <option>기관</option>
                      <option value="핵심인력">서비스 제공인력</option>
                      {service === "주야간보호" && <option>정원</option>}
                    </select>
                  </label>
                </div>
                <label>
                  전망기간 <strong>{horizon}년</strong>
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={horizon}
                    onChange={(e) => setHorizon(Number(e.target.value))}
                  />
                </label>
                <label>
                  시작할 때 한 번만 변경{" "}
                  <strong>
                    {timelineDelta > 0 ? `+${timelineDelta}` : timelineDelta}
                  </strong>
                  <input
                    type="range"
                    min={-10}
                    max={30}
                    value={timelineDelta}
                    onChange={(e) => setTimelineDelta(Number(e.target.value))}
                  />
                </label>
                <label>
                  이후 매년 반복 변경{" "}
                  <strong>
                    {annualAddition > 0 ? `+${annualAddition}` : annualAddition}
                  </strong>
                  <input
                    type="range"
                    min={-5}
                    max={10}
                    value={annualAddition}
                    onChange={(e) => setAnnualAddition(Number(e.target.value))}
                  />
                </label>
                <label>
                  연간 수요 변화율 <strong>{fmt(demandGrowth, 1)}%</strong>
                  <input
                    type="range"
                    min={-5}
                    max={15}
                    step={0.5}
                    value={demandGrowth}
                    onChange={(e) => setDemandGrowth(Number(e.target.value))}
                  />
                  <button
                    className="trend-button"
                    onClick={() =>
                      setDemandGrowth(
                        Math.max(-5, Math.min(15, observedDemandAnnual)),
                      )
                    }
                  >
                    관측 추세 {fmt(observedDemandAnnual, 1)}% 적용
                  </button>
                </label>
                <label>
                  수요 증가 가속 가정{" "}
                  <strong>매년 +{fmt(demandAcceleration, 1)}%p</strong>
                  <input
                    type="range"
                    min={0}
                    max={2}
                    step={0.1}
                    value={demandAcceleration}
                    onChange={(event) =>
                      setDemandAcceleration(Number(event.target.value))
                    }
                  />
                  <small>0보다 크면 연간 잠재수요 증가율이 해마다 설정한 %p만큼 높아지는 탐색 시나리오입니다.</small>
                  <small className="control-help">
                    0이면 같은 증가율을 유지합니다. 0보다 크면 잠재수요
                    증가율이 해마다 설정한 %p만큼 높아집니다.
                  </small>
                </label>
                <label>
                  연간 공급 변화율 <strong>{fmt(supplyGrowth, 1)}%</strong>
                  <input
                    type="range"
                    min={-10}
                    max={15}
                    step={0.5}
                    value={supplyGrowth}
                    onChange={(e) => setSupplyGrowth(Number(e.target.value))}
                  />
                  <button
                    className="trend-button"
                    onClick={() =>
                      setSupplyGrowth(
                        Math.max(-10, Math.min(15, observedSupplyAnnual)),
                      )
                    }
                  >
                    2023–2026 추세 {fmt(observedSupplyAnnual, 1)}% 적용
                  </button>
                </label>
              </section>

              <section className="timeline-output">
                <div className="scenario-title">
                  <div>
                    <p>{selectedRegionName?.sido_name}</p>
                    <h2>
                      {selectedRegionName?.sigungu_name} · {service}{" "}
                      {resourceLabel(resource)}
                    </h2>
                  </div>
                  <span>2026–{2026 + horizon}</span>
                </div>
                <div className="demand-forecast-note">
                  <span>수요 증가 가속을 반영한 시나리오 잠재수요</span>
                  <strong>
                    {fmt(timeline[0]?.demand || 0, 0)}명 →{" "}
                    {fmt(finalTimeline?.demand || 0, 0)}명
                  </strong>
                  <p>
                    시작 증가율 {fmt(demandGrowth, 1)}%에 매년{" "}
                    {fmt(demandAcceleration, 1)}%p를 더하는 사용자
                    시나리오입니다. 실제 인구추계나 통계적 예측값은 아닙니다.
                  </p>
                </div>
                <div className="scenario-carry-card">
                  <div>
                    <span>시간별로 적용한 자원 변경</span>
                    <strong>
                      시작연도에 {resourceLabel(resource)}{" "}
                      {timelineDelta > 0 ? `+${timelineDelta}` : timelineDelta}
                      {resourceUnit(resource)}
                    </strong>
                  </div>
                  <p>
                    현재 {formatResourceAmount(numberOrZero(selected?.current_resource), resource)}에서{" "}
                    {fmt(
                      Math.max(
                        0,
                        numberOrZero(selected?.current_resource) + timelineDelta,
                      ),
                      0,
                    )}
                    {resourceUnit(resource)}로 변경한 뒤, 이후 매년{" "}
                    {annualAddition > 0 ? `+${annualAddition}` : annualAddition}
                    {resourceUnit(resource)}씩 추가 변경하는 경우를 ‘변경 없음’과 비교합니다.
                  </p>
                </div>
                <div className="forecast-kpis">
                  <article>
                    <span>기간 동안 줄인 부족량</span>
                    <strong>{formatResourceAmount(cumulativeGapAvoided, resource, 1)}</strong>
                    <small>아무것도 바꾸지 않았을 때와 비교</small>
                  </article>
                  <article>
                    <span>마지막 해 부족량 감소</span>
                    <strong>{formatResourceAmount(finalGapImprovement, resource, 1)}</strong>
                    <small>변경 없음 대비 계산상 감소량</small>
                  </article>
                  <article>
                    <span>마지막 해 부족률</span>
                    <strong>
                      {pct(finalTimeline?.baselineShortage || 0)} →{" "}
                      {pct(finalTimeline?.scenarioShortage || 0)}
                    </strong>
                    <small>
                      {pct(finalShortageImprovement)}p 개선
                    </small>
                  </article>
                  <article>
                    <span>처음 탐색기준에 도달하는 해</span>
                    <strong>{targetYear ? `${targetYear}년` : "미도달"}</strong>
                    <small>전망기간 안 최초 시점</small>
                  </article>
                </div>
                <div className="timeline-chart-grid">
                  <TimelineChart
                    points={timeline}
                    baselineKey="baselineResource"
                    scenarioKey="scenarioResource"
                    title="연도별 자원 수"
                    baselineLabel="변경하지 않은 자원"
                    scenarioLabel="변경 시나리오 자원"
                    unit={resourceUnit(resource)}
                    takeaway={`마지막 해에 변경 시나리오의 자원이 ${formatResourceAmount((finalTimeline?.scenarioResource || 0) - (finalTimeline?.baselineResource || 0), resource, 1)} 더 많습니다.`}
                  />
                  <TimelineChart
                    points={timeline}
                    baselineKey="baselineGap"
                    scenarioKey="scenarioGap"
                    title="연도별 탐색기준 대비 계산상 격차"
                    baselineLabel="변경하지 않은 부족량"
                    scenarioLabel="변경 후 부족량"
                    unit={resourceUnit(resource)}
                    takeaway={`자원 변경으로 마지막 해의 부족량이 ${formatResourceAmount(finalGapImprovement, resource, 1)} 줄어듭니다.`}
                  />
                </div>
              </section>
            </div>
            <section className="panel timeline-table-panel">
              <div className="section-head">
                <div>
                  <span className="section-index">T</span>
                  <h2>해마다 수요와 자원이 어떻게 달라질까요?</h2>
                </div>
                <small>
                  수요는 복리 변화율, 공급은 관측 변화율과 계획 순증감을 적용
                </small>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>연도</th>
                      <th>시나리오 잠재수요</th>
                      <th>적용 수요증가율</th>
                      <th>조치하지 않을 때 자원</th>
                      <th>계획을 적용한 자원</th>
                      <th>자원 차이</th>
                      <th>조치하지 않을 때 부족량</th>
                      <th>계획 적용 후 부족량</th>
                      <th>부족량 감소</th>
                      <th>변경 없음 부족률</th>
                      <th>변경 후 부족률</th>
                      <th>탐색기준 상태 변화</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeline.map((row) => (
                      <tr key={row.year}>
                        <td className="rank-cell">{row.year}</td>
                        <td>{fmt(row.demand, 0)}</td>
                        <td>
                          {row.year === 2026
                            ? "기준연도"
                            : `${fmt(row.demandGrowthRate, 1)}%`}
                        </td>
                        <td>{fmt(row.baselineResource, 1)}</td>
                        <td>
                          <strong>{fmt(row.scenarioResource, 1)}</strong>
                        </td>
                        <td>{fmt(row.scenarioResource - row.baselineResource, 1)}</td>
                        <td>{fmt(row.baselineGap, 1)}</td>
                        <td>
                          <strong>{fmt(row.scenarioGap, 1)}</strong>
                        </td>
                        <td>{fmt(row.baselineGap - row.scenarioGap, 1)}</td>
                        <td>{pct(row.baselineShortage)}</td>
                        <td>{pct(row.scenarioShortage)}</td>
                        <td>
                          {row.baselineGap <= 1e-9 ? "탐색기준 이상" : "탐색기준 미만"} →{" "}
                          <strong>
                            {row.scenarioGap <= 1e-9 ? "탐색기준 이상" : "탐색기준 미만"}
                          </strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <p className="footnote">
              이 전망은 2022–2025 수요 추세와 2023–2026 공급 스냅샷을
              초기값으로 사용하는 결정적 시나리오입니다. 정책 인과효과나 실제
              미래값을 예측하는 통계·AI 모형이 아닙니다.
            </p>
          </>
        )}

        {view === "sensitivity" && (
          <>
            <InsightCallout
              title="같은 총량이라도 배치 기준에 따라 개선되는 지역과 줄어드는 부족량이 달라집니다."
              detail="각 전략 카드에서는 ‘몇 개 지역이 개선되는지’와 ‘부족량이 얼마나 감소하는지’ 두 숫자만 먼저 비교하세요."
            />
            <section className="allocation-builder">
              <div className="allocation-controls">
                <span className="section-index">자동</span>
                <h2>같은 자원 총량을 여러 기준으로 배치해 보세요</h2>
                <p>
                  서비스·자원·총량·지역당 상한은 같게 두고, 우선순위
                  기준만 바꿔 결과를 비교합니다.
                </p>
                <div className="inline-fields">
                  <label>
                    서비스
                    <select
                      value={service}
                      onChange={(event) => {
                        const next = event.target.value;
                        setService(next);
                        if (next !== "주야간보호" && resource === "정원")
                          setResource("기관");
                      }}
                    >
                      <option>방문요양</option>
                      <option>방문간호</option>
                      <option>주야간보호</option>
                    </select>
                  </label>
                  <label>
                    자원
                    <select
                      value={resource}
                      onChange={(event) => setResource(event.target.value)}
                    >
                      <option>기관</option>
                      <option value="핵심인력">서비스 제공인력</option>
                      {service === "주야간보호" && <option>정원</option>}
                    </select>
                  </label>
                </div>
                <label>
                  배치할 총량 <strong>{formatResourceAmount(allocationBudget, resource)}</strong>
                  <input
                    type="range"
                    min={1}
                    max={30}
                    value={allocationBudget}
                    onChange={(event) =>
                      setAllocationBudget(Number(event.target.value))
                    }
                  />
                </label>
                <label>
                  지역당 최대 <strong>{formatResourceAmount(allocationCap, resource)}</strong>
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={allocationCap}
                    onChange={(event) =>
                      setAllocationCap(Number(event.target.value))
                    }
                  />
                </label>
              </div>
              <div className="allocation-results">
                {automaticAllocations.map((result) => (
                  <article key={result.strategy}>
                    <header>
                      <div>
                        <span>{result.strategy}</span>
                        <strong>{formatResourceAmount(result.allocated, resource)} 배치</strong>
                      </div>
                      <small>
                        {result.improvedRegions}개 지역 · 부족량{" "}
                        {formatResourceAmount(result.gapReduction, resource, 1)} 감소
                      </small>
                    </header>
                    <div>
                      {result.items.slice(0, 6).map(({ row, allocated }) => (
                        <p key={row.region_code}>
                          <span>{row.sigungu_name}</span>
                          <b>+{formatResourceAmount(allocated, resource)}</b>
                        </p>
                      ))}
                    </div>
                    {result.remaining > 0 && (
                      <em>조건상 배치하지 못한 자원 {formatResourceAmount(result.remaining, resource)}</em>
                    )}
                  </article>
                ))}
              </div>
            </section>
            <div className="content-grid sensitivity-grid">
              <section className="panel mixed-unit-deprecation">
                <div className="section-head"><div><span className="section-index">04</span><h2>민감도는 순서의 안정성으로 확인합니다</h2></div></div>
                <p>과거 전역 부족량 합계는 단위가 다른 기관·서비스 제공인력·정원을 함께 더한 값이므로 공개 성과지표에서 사용 중단했습니다. 절대 격차 감소량은 위 자동배치처럼 선택한 서비스×자원 분석축 안에서만 비교합니다.</p>
              </section>
            <section className="panel">
              <div className="section-head">
                <div>
                  <span className="section-index">R</span>
                  <h2>조건이 달라도 결과가 비슷한가요?</h2>
                </div>
                <small>기본 조건(BASE)과 비교한 지역·순위의 유사성</small>
              </div>
              <div className="stability-list">
                {stability.map((row) => (
                  <article key={row.scenario_id}>
                    <strong>{row.scenario_id.replaceAll("_", " ")}</strong>
                    <div>
                      <span>탐색용 상위 10개 지역 일치율</span>
                      <b>{pct(numberOrZero(row.top10_urgency_jaccard))}</b>
                    </div>
                    <div>
                      <span>전체 탐색 순서 유사성</span>
                      <b>{fmt(numberOrZero(row.urgency_rank_spearman), 3)}</b>
                    </div>
                    <div>
                      <span>먼저 검토할 자원 일치율</span>
                      <b>{pct(numberOrZero(row.resource_recommendation_match_rate))}</b>
                    </div>
                  </article>
                ))}
              </div>
              </section>
            </div>
            <p className="footnote">
                  자동 배치는 동일 조건에서 생성한 계산안입니다. 지역 내부 기관이
                  미관측된 곳에는 인력·정원만 단독 배치하지 않으며, 실제 예산·채용·시설
              가능성을 확인한 뒤 사용해야 합니다. 아래 결과는 저장된 탐색적
              민감도 스냅샷을 요약한 값입니다.
            </p>
          </>
        )}

        {view === "access" && (
          <>
            <section className="target-definition access-caution">
              <strong>탐색적 확장 분석</strong>
              <p>실제 도로 이동시간이나 서비스 권역이 아니라 같은 도의 자원공유 가능성을 단순화해 살펴보는 탐색 시나리오입니다.</p>
            </section>
            <section className="metric-strip access-strip">
              <article>
                <span>같은 도에서 연결 가능한 관계</span>
                <strong>764</strong>
                <small>한 지역에서 다른 지역으로의 연결 수</small>
              </article>
              <article>
                <span>주변 자원으로 부족이 줄어든 지역</span>
                <strong>{relievedRegions}</strong>
                <small>76개 군 중</small>
              </article>
              <article>
                <span>자원을 바꾼 지역</span>
                <strong>{directImpacts.length}</strong>
                <small>보은군 기관 +1 예시</small>
              </article>
              <article>
                <span>함께 영향을 받은 주변 지역</span>
                <strong>{indirectImpacts.length}</strong>
                <small>같은 도 권역</small>
              </article>
            </section>
            <InsightCallout
              title={`외부공급 가정을 반영하면 ${relievedRegions}개 지역의 계산상 부족이 줄어듭니다.`}
              detail="이는 실제 이동이나 기관 수용 가능성을 확인한 결과가 아닙니다. 아래에서는 어느 외부지역이 얼마나 기여하는지만 확인하세요."
            />
            <div className="content-grid access-grid">
              <section className="panel">
                <div className="section-head">
                  <div>
                    <span className="section-index">05</span>
                    <h2>주변 지역 자원으로 줄어든 부족률</h2>
                  </div>
                  <small>다른 지역이 탐색기준을 채우고 남은 자원만 공유한다고 가정</small>
                </div>
                <div className="metric-bars">
                  {accessMetrics.map((row) => (
                    <div key={`${row.service}-${row.resource_type}`}>
                      <span>
                        <b>{row.service}</b>
                        <small>{resourceLabel(row.resource_type)}</small>
                      </span>
                      <Bar
                        value={numberOrZero(row.gap_relief_rate_before)}
                        max={1}
                        tone="cool"
                      />
                      <strong>{pct(numberOrZero(row.gap_relief_rate_before))}</strong>
                    </div>
                  ))}
                </div>
              </section>
              <section className="panel access-ranking">
                <div className="section-head">
                  <div>
                    <span className="section-index">G</span>
                    <h2>주변 자원의 도움을 가장 많이 받은 지역</h2>
                  </div>
                  <small>우리 지역만 볼 때의 부족량 − 주변 자원을 포함한 부족량</small>
                </div>
                {[...accessRegions]
                  .sort(
                    (a, b) => numberOrZero(b.total_access_relief) - numberOrZero(a.total_access_relief),
                  )
                  .slice(0, 10)
                  .map((row, index) => (
                    <div key={row.region_code}>
                      <b>{String(index + 1).padStart(2, "0")}</b>
                      <span>
                        <strong>{row.sigungu_name}</strong>
                        <small>{row.sido_name}</small>
                      </span>
                      <em>{fmt(numberOrZero(row.total_access_relief), 1)}</em>
                    </div>
                  ))}
              </section>
            </div>
            <section className="panel contribution-panel">
              <div className="section-head">
                <div>
                  <span className="section-index">기여</span>
                  <h2>선택 지역의 외부공급은 어디에서 오나요?</h2>
                </div>
                <select
                  aria-label="외부공급 확인 지역"
                  value={selectedRegion}
                  onChange={(event) => setSelectedRegion(event.target.value)}
                >
                  {[...visibleRegions]
                    .sort((a, b) =>
                      a.sigungu_name.localeCompare(b.sigungu_name, "ko"),
                    )
                    .map((row) => (
                      <option value={row.region_code} key={row.region_code}>
                        {row.sido_name} {row.sigungu_name}
                      </option>
                    ))}
                </select>
              </div>
              <div className="contribution-cards" aria-label="외부공급 주요 기여지역">
                {selectedContributions.slice(0, 3).map((row, index) => (
                  <article key={`${row.destination_region_code}-${index}`}>
                    <span>{index + 1}번째 기여지역</span>
                    <strong>
                      {contributionRegionName(row.destination_region_code)}
                    </strong>
                    <p>
                      {row.service} {resourceLabel(row.resource_type)}{" "}
                      <b>{fmt(numberOrZero(row.weighted_external_resource), 2)}</b> 반영
                    </p>
                  </article>
                ))}
              </div>
              <details className="detail-table">
                <summary>외부공급 상세 계산표 펼치기</summary>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>공급을 제공하는 외부지역</th>
                      <th>서비스</th>
                      <th>자원</th>
                      <th>외부지역 현재량</th>
                      <th>계산상 잉여량</th>
                      <th>가중치</th>
                      <th>최종 반영량</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedContributions.slice(0, 40).map((row, index) => (
                      <tr
                        key={`${row.destination_region_code}-${row.service}-${row.resource_type}-${index}`}
                      >
                        <td>
                          <strong>
                            {contributionRegionName(row.destination_region_code)}
                          </strong>
                        </td>
                        <td>{row.service}</td>
                        <td>{resourceLabel(row.resource_type)}</td>
                        <td>{fmt(numberOrZero(row.source_current_resource), 1)}</td>
                        <td>{fmt(numberOrZero(row.source_available_resource), 1)}</td>
                        <td>{fmt(numberOrZero(row.access_weight), 2)}</td>
                        <td className="inventory-number">
                          {fmt(numberOrZero(row.weighted_external_resource), 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              </details>
              {!selectedContributions.length && (
                <p className="empty-copy">
                  현재 설정에서 반영되는 외부 잉여공급이 없습니다.
                </p>
              )}
              <p className="inventory-note">
                최대 40개 기여관계를 표시합니다. 외부지역이 자기 탐색기준을
                충족하고 남긴 계산상 잉여량에 서비스별 탐색 가중치를 적용한
                값입니다.
              </p>
            </section>
            <p className="footnote">
              기존 자료에는 시군구 경계 인접행렬이 없어 같은 도 비인접 가중치만
              적용했습니다. 접근성 가중치는 공식 기준이 아닌 민감도 입력값입니다.
            </p>
          </>
        )}

        {view === "reports" && selectedRegionName && (
          <div className="report-page">
            <section className="report-toolbar">
              <div>
                <span className="section-index">출력</span>
                <h2>{selectedRegionName.sigungu_name} 진단 결과 내보내기</h2>
                <p>
                  화면의 선택 지역과 현재 기준선을 내려받습니다. PDF는 브라우저
                  인쇄 창에서 ‘PDF로 저장’을 선택하세요.
                </p>
              </div>
              <select
                value={selectedRegion}
                onChange={(event) => setSelectedRegion(event.target.value)}
              >
                {[...visibleRegions]
                  .sort((a, b) =>
                    a.sigungu_name.localeCompare(b.sigungu_name, "ko"),
                  )
                  .map((row) => (
                    <option value={row.region_code} key={row.region_code}>
                      {row.sido_name} {row.sigungu_name}
                    </option>
                  ))}
              </select>
              <button
                onClick={() =>
                  downloadCsv(
                    regionInventory,
                    `${selectedRegionName.sigungu_name}_자원진단.csv`,
                  )
                }
              >
                진단 CSV
              </button>
              <button
                onClick={() =>
                  downloadCsv(
                    selectedWorkforce,
                    `${selectedRegionName.sigungu_name}_직종별인력.csv`,
                  )
                }
              >
                인력 CSV
              </button>
              <button onClick={() => window.print()}>PDF로 저장</button>
            </section>

            <section className="quality-grid">
              {quality.map((row) => (
                <article key={row.dataset}>
                  <header>
                    <strong>{row.dataset}</strong>
                    <span className={`quality-status ${row.status}`}>
                      {row.status}
                    </span>
                  </header>
                  <p>{row.reference_date}</p>
                  <small>{row.coverage}</small>
                  <em>{row.warning}</em>
                </article>
              ))}
            </section>

            <section className="panel report-summary">
              <div className="section-head">
                <div>
                  <span className="section-index">요약</span>
                  <h2>보고서에 포함되는 핵심 근거</h2>
                </div>
                <small>화면·CSV·PDF 공통 해석 기준</small>
              </div>
              <div className="report-facts">
                <p>
                  <span>지역</span>
                  <strong>
                    {selectedRegionName.sido_name}{" "}
                    {selectedRegionName.sigungu_name}
                  </strong>
                </p>
                <p>
                  <span>장기요양 잠재수요 추정치</span>
                  <strong>{fmt(numberOrZero(selectedRegionName.ltci_demand), 0)}</strong>
                  <small>공개자료와 비공개 셀 범위를 반영한 추정 중앙값</small>
                </p>
                <p>
                  <span>가장 부족한 자원</span>
                  <strong>
                    {selectedRegionName.top_shortage_service} ·{" "}
                    {resourceLabel(
                      selectedRegionName.top_shortage_resource_type,
                    )}
                  </strong>
                </p>
                <p>
                  <span>현장검토 후보 순서</span>
                  <strong>{selectedRegionName.urgency_rank}위</strong>
                </p>
              </div>
              <p className="footnote">
                이 보고서는 공개자료 기반의 탐색 결과이며 실제 기관 운영,
                신규접수 가능성, 대기자, 이동시간, 설치비와 정책 인과효과를
                확인하지 않습니다.
              </p>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
