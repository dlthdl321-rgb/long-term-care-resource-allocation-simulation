$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$processedDir = Join-Path $projectRoot 'data\processed'
$analysisDir = Join-Path $projectRoot 'data\analysis_ready'
New-Item -ItemType Directory -Force -Path $analysisDir | Out-Null

function Convert-Count {
    param([object]$Value)
    if ($null -eq $Value -or $Value -eq '' -or $Value -eq '*') { return 0L }
    return [long](($Value.ToString()) -replace ',', '')
}

# 읍면동별 고령인구 지표
$populationPath = Join-Path $processedDir 'population_age_sex_admin_dong_202606.csv'
$population = Import-Csv -LiteralPath $populationPath -Encoding UTF8
$elderlyRows = foreach ($row in $population) {
    $male65 = 0L; $female65 = 0L
    $male75 = 0L; $female75 = 0L
    $male85 = 0L; $female85 = 0L

    foreach ($age in 65..109) {
        $male = Convert-Count $row."${age}세남자"
        $female = Convert-Count $row."${age}세여자"
        $male65 += $male; $female65 += $female
        if ($age -ge 75) { $male75 += $male; $female75 += $female }
        if ($age -ge 85) { $male85 += $male; $female85 += $female }
    }

    $male110 = Convert-Count $row.'110세이상 남자'
    $female110 = Convert-Count $row.'110세이상 여자'
    $male65 += $male110; $female65 += $female110
    $male75 += $male110; $female75 += $female110
    $male85 += $male110; $female85 += $female110
    $total = Convert-Count $row.계
    $elderly65 = $male65 + $female65

    [pscustomobject]@{
        행정기관코드 = $row.행정기관코드
        기준연월 = $row.기준연월
        시도명 = $row.시도명
        시군구명 = $row.시군구명
        읍면동명 = $row.읍면동명
        총인구 = $total
        '65세이상인구' = $elderly65
        '75세이상인구' = $male75 + $female75
        '85세이상인구' = $male85 + $female85
        '65세이상남자' = $male65
        '65세이상여자' = $female65
        고령화율 = if ($total -gt 0) { [math]::Round($elderly65 / $total * 100, 4) } else { $null }
    }
}
$elderlyRows | Export-Csv -LiteralPath (Join-Path $analysisDir 'elderly_population_admin_dong_202606.csv') -NoTypeInformation -Encoding UTF8

# 시군구별 장기요양 수요 지표. '*'는 5명 미만 비공개 셀이므로 합계에서 0으로 처리하고 개수를 별도 보존한다.
$ltciPath = Join-Path $processedDir 'ltci_grade_decisions_sigungu_202605.csv'
$ltci = Import-Csv -LiteralPath $ltciPath -Encoding UTF8
$gradeColumns = @('1등급', '2등급', '3등급', '4등급', '5등급', '인지지원등급')
$ltciRows = foreach ($group in ($ltci | Group-Object 시도, 시군구)) {
    $first = $group.Group[0]
    $knownApplicants = 0L
    $knownRecognized = 0L
    $suppressedCells = 0

    foreach ($row in $group.Group) {
        if ($row.신청자 -eq '*') { $suppressedCells++ } else { $knownApplicants += Convert-Count $row.신청자 }
        foreach ($column in $gradeColumns) {
            if ($row.$column -eq '*') { $suppressedCells++ } else { $knownRecognized += Convert-Count $row.$column }
        }
    }

    [pscustomobject]@{
        시도 = $first.시도
        시군구 = $first.시군구
        신청자_공개값합계 = $knownApplicants
        인정자_공개값합계 = $knownRecognized
        비공개셀수 = $suppressedCells
        자료기준 = '2026-05-31'
    }
}
$ltciRows | Export-Csv -LiteralPath (Join-Path $analysisDir 'ltci_demand_sigungu_202605.csv') -NoTypeInformation -Encoding UTF8

Write-Output "Created $($elderlyRows.Count) population rows and $($ltciRows.Count) LTCI rows."
