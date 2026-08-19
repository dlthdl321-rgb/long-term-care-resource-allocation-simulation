import assert from "node:assert/strict";
import { access, readFile, readdir } from "node:fs/promises";
import test from "node:test";

async function render() {
  const html = await readFile(new URL("../dist-public/index.html", import.meta.url), "utf8");
  return new Response(html, { status: 200, headers: { "content-type": "text/html; charset=utf-8" } });
}

test("server-renders the dashboard shell and production metadata", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /lang="ko"/);
  assert.match(html, /<title>돌봄자원 랩 \| 장기요양 자원배치 의사결정 시뮬레이터<\/title>/);
  assert.match(html, /<div id="root"><\/div>/);
  assert.match(html, /property="og:title"/);
  assert.match(html, /twitter:card/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/);
});

test("ships complete 76-county data and interactive dashboard code", async () => {
  const [
    regionsRaw,
    baselineRaw,
    trendsRaw,
    workforceRaw,
    historyRaw,
    contributionsRaw,
    portfolioSummaryRaw,
    page,
    packageJson,
    fieldSupport,
    formatSource,
    rootReadme,
    caseStudy,
    overviewSource,
    timelineChartSource,
  ] = await Promise.all([
    readFile(new URL("../public/data/regions.json", import.meta.url), "utf8"),
    readFile(new URL("../public/data/baseline.json", import.meta.url), "utf8"),
    readFile(new URL("../public/data/supply-trends.json", import.meta.url), "utf8"),
    readFile(new URL("../public/data/workforce.json", import.meta.url), "utf8"),
    readFile(new URL("../public/data/history.json", import.meta.url), "utf8"),
    readFile(
      new URL("../public/data/access-contributions.json", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../public/data/portfolio-summary.json", import.meta.url), "utf8"),
    readFile(new URL("../src/App.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../src/lib/field-support.ts", import.meta.url), "utf8"),
    readFile(new URL("../src/lib/format.ts", import.meta.url), "utf8"),
    readFile(new URL("../../README.md", import.meta.url), "utf8"),
    readFile(new URL("../../CASE_STUDY.md", import.meta.url), "utf8"),
    readFile(new URL("../src/views/Overview.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/components/TimelineChart.tsx", import.meta.url), "utf8"),
  ]);

  const regions = JSON.parse(regionsRaw);
  const baseline = JSON.parse(baselineRaw);
  const trends = JSON.parse(trendsRaw);
  const workforce = JSON.parse(workforceRaw);
  const history = JSON.parse(historyRaw);
  const contributions = JSON.parse(contributionsRaw);
  const [portfolioSummary] = JSON.parse(portfolioSummaryRaw);
  assert.equal(regions.length, 76);
  assert.equal(baseline.length, 532);
  assert.equal(trends.length, 532);
  assert.ok(workforce.length >= 190);
  assert.ok(history.length >= 270);
  assert.equal(contributions.length, 5348);
  assert.equal(portfolioSummary.region_count, "76");
  assert.equal(portfolioSummary.resource_dimension_count, "7");
  assert.equal(portfolioSummary.visit_nursing_provider_missing, "28");
  assert.equal(
    baseline.filter(
      (row) =>
        row.service === "방문간호" &&
        row.resource_type === "기관" &&
        row.provider_missing === "True",
    ).length,
    28,
  );
  assert.match(page, /자원을 얼마나 바꿀까요/);
  assert.match(page, /주변 지역 자원으로 줄어든 부족률/);
  assert.match(page, /과거·미래 변화/);
  assert.match(page, /결정적 시나리오/);
  assert.match(page, /화면 읽는 법/);
  const dashboardSource = `${page}\n${overviewSource}\n${timelineChartSource}`;
  assert.match(dashboardSource, /PUBLIC DATA · ANALYTICS PORTFOLIO/);
  assert.match(dashboardSource, /전략 비교를 뒷받침하는 두 가지 근거/);
  assert.match(dashboardSource, /원자료에서 의사결정 화면까지/);
  assert.doesNotMatch(page, /프로젝트 기간/);
  assert.doesNotMatch(page, /확인 필요/);
  assert.match(page, /0%면 탐색기준 이상, 100%면 공급이 없는 상태/);
  assert.doesNotMatch(page, /baseline\.reduce\(\(sum, r\) => sum \+ num\(r\.integer_need\)/);
  assert.doesNotMatch(page, /30초 데모/);
  assert.match(dashboardSource, /핵심 전략 비교/);
  assert.match(page, /잠재수요 추정치/);
  assert.match(page, /탐색기준/);
  assert.doesNotMatch(page, /계산상 기관·인력·정원 합계/);
  assert.match(dashboardSource, /WHAT I BUILT/);
  assert.match(page, /현재 보유 수/);
  assert.match(page, /서비스 제공인력/);
  assert.match(page, /한 장 진단서/);
  assert.doesNotMatch(page, /개선되는 지역과 악화되는 지역/);
  assert.match(page, /선택 지역 직접효과만 기본 결과로 표시합니다/);
  assert.match(page, /같은 자원 총량을 여러 기준으로 배치/);
  assert.match(page, /PDF로 저장/);
  assert.match(page, /외부공급은 어디에서 오나요/);
  assert.match(page, /공급수준 중앙값을 탐색 기준/);
  assert.match(page, /수요 증가 가속 가정/);
  assert.doesNotMatch(page, /고령화 가속 가정/);
  assert.match(page, /demandAcceleration/);
  assert.match(page, /이 변경을 시간별로 비교하기/);
  assert.match(page, /연도별 자원 수/);
  assert.match(page, /연도별 탐색기준 대비 계산상 격차/);
  assert.match(page, /baselineShortage/);
  assert.match(page, /scenarioShortage/);
  assert.match(page, /탐색기준 상태 변화/);
  assert.match(page, /현장 검토/);
  assert.match(page, /실무 검토 요약/);
  assert.match(page, /탐색기준을 바꾸면 판단이 달라질까요/);
  assert.match(page, /현장에서 자주 검토할 변경안/);
  assert.match(page, /사전 시나리오 의사결정표/);
  assert.match(page, /회의 전 검토 체크리스트/);
  assert.match(page, /field-support/);
  assert.match(page, /InsightCallout/);
  assert.match(dashboardSource, /chart-end-values/);
  assert.match(page, /시나리오별 상세 수치 펼치기/);
  assert.match(page, /외부공급 상세 계산표 펼치기/);
  assert.match(page, /종합 지역취약성 탐색점수는 어떻게 계산하나요/);
  assert.match(page, /종합 취약성 탐색 백분위/);
  assert.match(page, /지역취약성 점수와 종합 탐색점수의 차이/);
  assert.match(page, /VULNERABILITY_COMPONENTS/);
  assert.match(dashboardSource, /forecast-line baseline/);
  assert.doesNotMatch(page, /scenario-point/);
  assert.match(page, /visibleRegions\.some/);
  assert.match(page, /setSelectedRegion\(visibleRegions\[0\]\.region_code\)/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.doesNotMatch(packageJson, /drizzle-(orm|kit)|db:generate/);
  assert.doesNotMatch(page, /row\.continuous_gap_reduction|row\.integer_need_reduction/);
  assert.match(page, /과거 전역 부족량 합계는 단위가 다른 기관·서비스 제공인력·정원을 함께 더한 값/);
  const publicCopy = `${dashboardSource}\n${fieldSupport}\n${rootReadme}\n${caseStudy}`;
  for (const forbidden of ["30초 데모", "수혜 인정자", "지원 시급성 순위", "기본목표", "상향목표", "목표미달", "목표 미달", "목표충족", "목표기준", "기관이 없는 군", "고령화 가속", "계산상 기관·인력·정원 합계"]) {
    assert.doesNotMatch(publicCopy, new RegExp(forbidden));
  }
  for (const required of ["한정된 장기요양 자원", "대표 5개소·4개 전략 비교하기", "배치 대상지역 잠재수요 합계", "기관 미관측 상태", "탐색기준", "종합 탐색점수", "장기요양 잠재수요 추정치", "탐색적 확장 분석"]) {
    assert.match(publicCopy, new RegExp(required));
  }
  assert.match(page, /formatResourceAmount/);
  assert.match(page, /resourceUnit/);
  assert.match(formatSource, /resourceType === "기관" \? "개소" : "명"/);
  assert.doesNotMatch(page, /unit="개"|result\.allocated\}개|current_resource\), 0\)\}개/);
  assert.doesNotMatch(page, /false &&/);
  assert.doesNotMatch(publicCopy, /방문간호기관 5개(?!소|의)/);
  for (const misleading of ["수혜 인정자", "실제 수혜자", "기관이 없는 지역", "최적 전략"]) {
    assert.doesNotMatch(publicCopy, new RegExp(misleading));
  }
});

test("portfolio summary, representative scenario, and documentation links stay consistent", async () => {
  const [baselineRaw, summaryRaw] = await Promise.all([
    readFile(new URL("../public/data/baseline.json", import.meta.url), "utf8"),
    readFile(new URL("../public/data/portfolio-summary.json", import.meta.url), "utf8"),
  ]);
  const baseline = JSON.parse(baselineRaw);
  const [summary] = JSON.parse(summaryRaw);
  const missing = baseline.filter((row) => row.service === "방문간호" && row.resource_type === "기관" && row.provider_missing === "True");
  assert.equal(missing.length, Number(summary.visit_nursing_provider_missing));
  const demo = baseline.find((row) => row.region_code === "48890" && row.service === "방문간호" && row.resource_type === "기관");
  assert.ok(demo);
  assert.equal(Number(demo.current_resource), 0);
  assert.equal(Math.max(0, Number(demo.target_resource) - (Number(demo.current_resource) + 1)), 0);
  await Promise.all([
    access(new URL("../../README.md", import.meta.url)),
    access(new URL("../../CASE_STUDY.md", import.meta.url)),
    access(new URL("../../03_데이터/outputs/hypothesis_testing/q1_vulnerability_supply_spearman.csv", import.meta.url)),
  ]);
});

test("public build contains current hero and excludes obsolete demo copy", async () => {
  const assetDir = new URL("../dist-public/assets/", import.meta.url);
  const files = await readdir(assetDir);
  const js = files.filter((name) => name.endsWith(".js"));
  assert.ok(js.length > 0);
  const bundle = (await Promise.all(js.map((name) => readFile(new URL(name, assetDir), "utf8")))).join("\n");
  assert.match(bundle, /한정된 장기요양 자원/);
  assert.match(bundle, /대표 5개소·4개 전략 비교하기/);
  assert.doesNotMatch(bundle, /30초 데모 보기/);
});
