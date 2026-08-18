import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the dashboard shell and production metadata", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /lang="ko"/);
  assert.match(html, /<title>돌봄자원 랩 \| 장기요양 자원배치 의사결정 시뮬레이터<\/title>/);
  assert.match(html, /실데이터를 불러오는 중입니다/);
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
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
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
  assert.match(page, /PUBLIC DATA · ANALYTICS PORTFOLIO/);
  assert.match(page, /숫자보다 먼저 읽는 핵심 발견/);
  assert.match(page, /원자료에서 의사결정 화면까지/);
  assert.doesNotMatch(page, /프로젝트 기간/);
  assert.doesNotMatch(page, /확인 필요/);
  assert.match(page, /0%면 탐색기준 이상, 100%면 공급이 없는 상태/);
  assert.doesNotMatch(page, /baseline\.reduce\(\(sum, r\) => sum \+ num\(r\.integer_need\)/);
  assert.match(page, /30초 데모 보기/);
  assert.match(page, /WHAT I BUILT/);
  assert.match(page, /현재 보유 수/);
  assert.match(page, /서비스 제공인력/);
  assert.match(page, /한 장 진단서/);
  assert.match(page, /개선되는 지역과 악화되는 지역/);
  assert.match(page, /같은 자원 총량을 여러 기준으로 배치/);
  assert.match(page, /PDF로 저장/);
  assert.match(page, /외부공급은 어디에서 오나요/);
  assert.match(page, /공급수준 중앙값을 탐색 기준/);
  assert.match(page, /고령화 가속 가정/);
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
  assert.match(page, /한눈에 보는 결론/);
  assert.match(page, /chart-end-values/);
  assert.match(page, /시나리오별 상세 수치 펼치기/);
  assert.match(page, /외부공급 상세 계산표 펼치기/);
  assert.match(page, /지역취약성 점수는 어떻게 계산하나요/);
  assert.match(page, /취약성 백분위/);
  assert.match(page, /지역취약성 점수와 지원 시급성 점수의 차이/);
  assert.match(page, /VULNERABILITY_COMPONENTS/);
  assert.match(page, /forecast-line baseline/);
  assert.doesNotMatch(page, /scenario-point/);
  assert.match(page, /visibleRegions\.some/);
  assert.match(page, /setSelectedRegion\(visibleRegions\[0\]\.region_code\)/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});
