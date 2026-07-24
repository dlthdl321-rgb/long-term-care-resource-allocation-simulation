param(
    [Parameter(Mandatory = $true)]
    [string]$ServiceKey,
    [int]$RowsPerPage = 1000
)

$ErrorActionPreference = "Stop"
$baseUrl = "https://apis.data.go.kr/B554287/sclWlfrFcltInfoInqirService1/getNFcltBizInqire"
$projectRoot = Split-Path -Parent $PSScriptRoot
$rawDir = Join-Path $projectRoot "data\raw\social_welfare_facilities_xml"
$processedPath = Join-Path $projectRoot "data\processed\social_welfare_facility_list_20260723.csv"
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null

function Get-Page([int]$PageNo) {
    $rawPath = Join-Path $rawDir ("social_welfare_facilities_page_{0:D3}.xml" -f $PageNo)
    if (Test-Path -LiteralPath $rawPath) {
        [xml]$cached = [IO.File]::ReadAllText($rawPath, [Text.Encoding]::UTF8)
        if ($cached.response.header.resultCode -eq "00") {
            return $cached
        }
    }
    $uri = $baseUrl +
        "?serviceKey=" + [uri]::EscapeDataString($ServiceKey) +
        "&pageNo=$PageNo&numOfRows=$RowsPerPage"
    $response = Invoke-WebRequest -UseBasicParsing -Uri $uri -TimeoutSec 60
    $content = $response.Content
    if ($content.Contains("ì") -or $content.Contains("ë")) {
        $content = [Text.Encoding]::UTF8.GetString(
            [Text.Encoding]::GetEncoding(28591).GetBytes($content)
        )
    }
    [xml]$xml = $content
    if ($xml.response.header.resultCode -ne "00") {
        throw "API error on page ${PageNo}: $($xml.response.header.resultCode) $($xml.response.header.resultMsg)"
    }
    [IO.File]::WriteAllText($rawPath, $content, [Text.UTF8Encoding]::new($false))
    return $xml
}

$first = Get-Page 1
$totalCount = [int]$first.response.body.totalCount
$pageCount = [int][Math]::Ceiling($totalCount / $RowsPerPage)
$rows = [Collections.Generic.List[object]]::new()

for ($page = 1; $page -le $pageCount; $page++) {
    $xml = if ($page -eq 1) { $first } else { Get-Page $page }
    foreach ($item in @($xml.response.body.items.item)) {
        $rows.Add([pscustomobject]@{
            facility_code = [string]$item.fcltCd
            facility_name = [string]$item.fcltNm
            facility_type_code = [string]$item.fcltKindCd
            facility_type_name = [string]$item.fcltKindNm
            certification_flag = [string]$item.certYn
            facility_status_code = [string]$item.fcltStatus
        })
    }
}

$rows | Export-Csv -LiteralPath $processedPath -NoTypeInformation -Encoding UTF8

[pscustomobject]@{
    collected_at = (Get-Date).ToString("s")
    total_count_from_api = $totalCount
    rows_saved = $rows.Count
    pages_saved = $pageCount
    unique_facility_codes = @($rows.facility_code | Sort-Object -Unique).Count
    processed_file = $processedPath
} | ConvertTo-Json
