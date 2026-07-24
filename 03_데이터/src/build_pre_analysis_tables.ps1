$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$data = Join-Path $root 'data'
$analysis = Join-Path $data 'analysis_ready'
$processed = Join-Path $data 'processed'

function Convert-Long([object]$value) {
    $number = 0L
    if ([long]::TryParse([string]$value, [ref]$number)) { return $number }
    return 0L
}

# SGIS 2025-06 administrative-code workbook: one row per administrative dong.
$sgis = Import-Csv (Join-Path $processed 'sgis_admin_code_202506.csv')
$regionReference = $sgis |
    Group-Object 시도코드, 시군구코드 |
    ForEach-Object {
        $row = $_.Group[0]
        [pscustomobject]@{
            SGIS_시도코드 = $row.시도코드
            SGIS_시군구코드 = $row.시군구코드
            SGIS_시군구결합코드 = "$($row.시도코드)$($row.시군구코드)"
            시도명 = $row.시도명칭
            시군구명 = $row.시군구명칭
            전체지역명 = "$($row.시도명칭) $($row.시군구명칭)"
            기준시점 = '2025-06'
        }
    } |
    Sort-Object SGIS_시도코드, SGIS_시군구코드
$regionReference | Export-Csv (Join-Path $analysis 'region_reference_sigungu_202506.csv') -NoTypeInformation -Encoding utf8

# Aggregate current population from administrative-dong to the source's sigungu level.
$population = Import-Csv (Join-Path $analysis 'elderly_population_admin_dong_202606.csv')
$populationSigungu = $population |
    Group-Object 시도명, 시군구명 |
    ForEach-Object {
        $row = $_.Group[0]
        $total = ($_.Group | Measure-Object 총인구 -Sum).Sum
        $age65 = ($_.Group | Measure-Object '65세이상인구' -Sum).Sum
        [pscustomobject]@{
            주민등록_시군구코드 = ([string]$row.행정기관코드).Substring(0, 5)
            기준연월 = $row.기준연월
            시도명 = $row.시도명
            시군구명 = $row.시군구명
            총인구 = [long]$total
            '65세이상인구' = [long]$age65
            '75세이상인구' = [long](($_.Group | Measure-Object '75세이상인구' -Sum).Sum)
            '85세이상인구' = [long](($_.Group | Measure-Object '85세이상인구' -Sum).Sum)
            '65세이상남자' = [long](($_.Group | Measure-Object '65세이상남자' -Sum).Sum)
            '65세이상여자' = [long](($_.Group | Measure-Object '65세이상여자' -Sum).Sum)
            고령화율 = if ($total -gt 0) { [math]::Round($age65 / $total * 100, 4) } else { $null }
        }
    } |
    Sort-Object 시도명, 시군구명
$populationSigungu | Export-Csv (Join-Path $analysis 'elderly_population_sigungu_202606.csv') -NoTypeInformation -Encoding utf8

# Aggregate elderly single-person households from legal-dong to sigungu.
$single = Import-Csv (Join-Path $analysis 'elderly_single_person_households_legal_dong_202606.csv')
$singleSigungu = $single |
    Group-Object 시도명, 시군구명 |
    ForEach-Object {
        $row = $_.Group[0]
        [pscustomobject]@{
            법정동_시군구코드 = ([string]$row.법정동코드).Substring(0, 5)
            기준연월 = $row.기준연월
            시도명 = $row.시도명
            시군구명 = $row.시군구명
            '65세이상1인세대' = [long](($_.Group | Measure-Object '65세이상1인세대' -Sum).Sum)
            '65세이상남자1인세대' = [long](($_.Group | Measure-Object '65세이상남자1인세대' -Sum).Sum)
            '65세이상여자1인세대' = [long](($_.Group | Measure-Object '65세이상여자1인세대' -Sum).Sum)
        }
    } |
    Sort-Object 시도명, 시군구명
$singleSigungu | Export-Csv (Join-Path $analysis 'elderly_single_person_households_sigungu_202606.csv') -NoTypeInformation -Encoding utf8

# Preserve uncertainty caused by cells suppressed when the count is below five.
$demandRaw = Import-Csv (Join-Path $processed 'ltci_grade_decisions_sigungu_202605.csv')
$gradeColumns = @('1등급', '2등급', '3등급', '4등급', '5등급', '인지지원등급')
$demandBounds = $demandRaw |
    Group-Object 시도, 시군구 |
    ForEach-Object {
        $row = $_.Group[0]
        $knownApplicants = 0L
        $knownRecognized = 0L
        $suppressedApplicants = 0
        $suppressedRecognized = 0
        foreach ($item in $_.Group) {
            if ($item.신청자 -eq '*') { $suppressedApplicants++ }
            else { $knownApplicants += Convert-Long $item.신청자 }
            foreach ($column in $gradeColumns) {
                if ($item.$column -eq '*') { $suppressedRecognized++ }
                else { $knownRecognized += Convert-Long $item.$column }
            }
        }
        [pscustomobject]@{
            시도 = $row.시도
            시군구 = $row.시군구
            신청자_공개값합계 = $knownApplicants
            신청자_비공개셀수 = $suppressedApplicants
            신청자_추정하한 = $knownApplicants + $suppressedApplicants
            신청자_추정상한 = $knownApplicants + 4 * $suppressedApplicants
            인정자_공개값합계 = $knownRecognized
            인정자_비공개셀수 = $suppressedRecognized
            인정자_추정하한 = $knownRecognized + $suppressedRecognized
            인정자_추정상한 = $knownRecognized + 4 * $suppressedRecognized
            자료기준 = '2026-05-31'
        }
    } |
    Sort-Object 시도, 시군구
$demandBounds | Export-Csv (Join-Path $analysis 'ltci_demand_sigungu_bounds_202605.csv') -NoTypeInformation -Encoding utf8

# Attach geographic location from the facility-general table. Do not use the
# search API's regional code as a location: it can represent an administrative
# branch rather than the facility's physical address.
$facilityDir = Join-Path $processed 'ltci_facility_status_20260610'
$general = Import-Csv (Join-Path $facilityDir 'ltci_facility_general_20260610.csv')
$capacity = Import-Csv (Join-Path $facilityDir 'ltci_facility_capacity_20260610.csv')
$staff = Import-Csv (Join-Path $facilityDir 'ltci_facility_staff_20260610.csv')
$geoByInstitution = @{}
$regionNameByCode = @{}
foreach ($row in $general) {
    if ($row.시도코드 -and $row.시군구코드 -and $row.'시도 시군구 법정동명') {
        $parts = ([string]$row.'시도 시군구 법정동명').Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
        $sigunguName = if ($parts.Count -ge 2) { $parts[1] } else { '' }
        if ($parts.Count -ge 3 -and $parts[1] -match '시$' -and $parts[2] -match '구$') {
            $sigunguName = "$($parts[1]) $($parts[2])"
        }
        $regionNameByCode["$($row.시도코드)$($row.시군구코드)"] = [pscustomobject]@{
            시도명 = if ($parts.Count -ge 1) { $parts[0] } else { '' }
            시군구명 = $sigunguName
        }
    }
}
foreach ($row in $general) {
    if ($row.시도코드 -and $row.시군구코드 -and -not $geoByInstitution.ContainsKey($row.장기요양기관코드)) {
        $parts = ([string]$row.'시도 시군구 법정동명').Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
        $sigunguName = if ($parts.Count -ge 2) { $parts[1] } else { '' }
        if ($parts.Count -ge 3 -and $parts[1] -match '시$' -and $parts[2] -match '구$') {
            $sigunguName = "$($parts[1]) $($parts[2])"
        }
        $regionCode = "$($row.시도코드)$($row.시군구코드)"
        $fallback = $regionNameByCode[$regionCode]
        $geoByInstitution[$row.장기요양기관코드] = [pscustomobject]@{
            지역코드 = $regionCode
            시도명 = if ($parts.Count -ge 1) { $parts[0] } else { $fallback.시도명 }
            시군구명 = if ($sigunguName) { $sigunguName } else { $fallback.시군구명 }
        }
    }
}

$capacityGeo = foreach ($row in $capacity) {
    $geo = $geoByInstitution[$row.장기요양기관코드]
    if ($null -ne $geo) {
        [pscustomobject]@{
            지역코드 = $geo.지역코드
            시도명 = $geo.시도명
            시군구명 = $geo.시군구명
            장기요양기관코드 = $row.장기요양기관코드
            기관유형코드 = $row.기관유형코드
            기관유형명 = $row.기관유형명
            정원 = Convert-Long $row.정원
        }
    }
}
$staffGeo = foreach ($row in $staff) {
    $geo = $geoByInstitution[$row.장기요양기관코드]
    if ($null -ne $geo) {
        [pscustomobject]@{
            지역코드 = $geo.지역코드
            시도명 = $geo.시도명
            시군구명 = $geo.시군구명
            장기요양기관코드 = $row.장기요양기관코드
            기관유형코드 = $row.기관유형코드
            기관유형명 = $row.기관유형코드명
            사회복지사 = Convert-Long $row.사회복지사
            간호사 = Convert-Long $row.간호사
            간호조무사 = Convert-Long $row.간호조무사
            물리치료사 = Convert-Long $row.물리치료사
            작업치료사 = Convert-Long $row.작업치료사
            요양보호사 = Convert-Long $row.요양보호사
        }
    }
}

$supplyKeys = @(
    $capacityGeo | ForEach-Object { "$($_.지역코드)|$($_.기관유형코드)" }
    $staffGeo | ForEach-Object { "$($_.지역코드)|$($_.기관유형코드)" }
) | Sort-Object -Unique
$capacityGroups = $capacityGeo | Group-Object { "$($_.지역코드)|$($_.기관유형코드)" } -AsHashTable -AsString
$staffGroups = $staffGeo | Group-Object { "$($_.지역코드)|$($_.기관유형코드)" } -AsHashTable -AsString

$supply = foreach ($key in $supplyKeys) {
    $capacityRows = @($capacityGroups[$key] | Where-Object { $null -ne $_ })
    $staffRows = @($staffGroups[$key] | Where-Object { $null -ne $_ })
    $sample = if ($capacityRows.Count -gt 0) { $capacityRows[0] } else { $staffRows[0] }
    [pscustomobject]@{
        시설_지역코드 = $sample.지역코드
        시도명 = $sample.시도명
        시군구명 = $sample.시군구명
        기관유형코드 = $sample.기관유형코드
        기관유형명 = $sample.기관유형명
        기관수 = (@($capacityRows.장기요양기관코드 + $staffRows.장기요양기관코드) | Sort-Object -Unique).Count
        정원 = [long](($capacityRows | Measure-Object 정원 -Sum).Sum)
        사회복지사 = [long](($staffRows | Measure-Object 사회복지사 -Sum).Sum)
        간호사 = [long](($staffRows | Measure-Object 간호사 -Sum).Sum)
        간호조무사 = [long](($staffRows | Measure-Object 간호조무사 -Sum).Sum)
        물리치료사 = [long](($staffRows | Measure-Object 물리치료사 -Sum).Sum)
        작업치료사 = [long](($staffRows | Measure-Object 작업치료사 -Sum).Sum)
        요양보호사 = [long](($staffRows | Measure-Object 요양보호사 -Sum).Sum)
        자료기준 = '2026-06-10'
    }
}
$supply |
    Sort-Object 시설_지역코드, 기관유형코드 |
    Export-Csv (Join-Path $analysis 'ltci_supply_sigungu_service_type_20260610.csv') -NoTypeInformation -Encoding utf8

# Historical occupancy is retained separately because the current 2026 file
# no longer publishes current residents. It is a sensitivity prior, not a
# current utilization measure.
$historicalDir = Join-Path $processed 'ltci_facility_status_20250401'
$historicalGeneral = Import-Csv (Join-Path $historicalDir 'ltci_facility_general_20250401.csv')
$historicalOccupancy = Import-Csv (Join-Path $historicalDir 'ltci_facility_occupancy_20250401.csv')
$historicalGeo = @{}
foreach ($row in $historicalGeneral) {
    if ($row.시도코드 -and $row.시군구코드 -and -not $historicalGeo.ContainsKey($row.장기요양기관코드)) {
        $parts = ([string]$row.'시도 시군구 법정동명').Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
        $sigunguName = if ($parts.Count -ge 2) { $parts[1] } else { '' }
        if ($parts.Count -ge 3 -and $parts[1] -match '시$' -and $parts[2] -match '구$') {
            $sigunguName = "$($parts[1]) $($parts[2])"
        }
        $historicalGeo[$row.장기요양기관코드] = [pscustomobject]@{
            지역코드 = "$($row.시도코드)$($row.시군구코드)"
            시도명 = if ($parts.Count -ge 1) { $parts[0] } else { '' }
            시군구명 = $sigunguName
        }
    }
}
$historicalOccupancyGeo = foreach ($row in $historicalOccupancy) {
    $geo = $historicalGeo[$row.장기요양기관코드]
    if ($null -ne $geo) {
        $capacityValue = Convert-Long $row.정원
        $currentValue = if ($row.현원 -eq '') { $null } else { Convert-Long $row.현원 }
        [pscustomobject]@{
            지역코드 = $geo.지역코드
            시도명 = $geo.시도명
            시군구명 = $geo.시군구명
            장기요양기관코드 = $row.장기요양기관코드
            기관유형코드 = $row.기관유형코드
            기관유형명 = $row.기관유형명
            정원 = $capacityValue
            현원 = $currentValue
        }
    }
}
$historicalOccupancySummary = $historicalOccupancyGeo |
    Group-Object 지역코드, 기관유형코드 |
    ForEach-Object {
        $row = $_.Group[0]
        $knownCurrent = @($_.Group | Where-Object { $null -ne $_.현원 })
        $capacitySum = [long](($knownCurrent | Measure-Object 정원 -Sum).Sum)
        $currentSum = [long](($knownCurrent | Measure-Object 현원 -Sum).Sum)
        $capacityConstrained = $row.기관유형코드 -match '^(A|G|H|I|M|S)' -or
            $row.기관유형코드 -in @('B03', 'B04', 'C03', 'C04')
        [pscustomobject]@{
            시설_지역코드 = $row.지역코드
            시도명 = $row.시도명
            시군구명 = $row.시군구명
            기관유형코드 = $row.기관유형코드
            기관유형명 = $row.기관유형명
            기관수 = ($_.Group.장기요양기관코드 | Sort-Object -Unique).Count
            현원확인기관수 = ($knownCurrent.장기요양기관코드 | Sort-Object -Unique).Count
            현원결측행수 = ($_.Group | Where-Object { $null -eq $_.현원 }).Count
            정원합계_현원확인기관 = $capacitySum
            현원합계 = $currentSum
            원자료_현원정원비 = if ($capacitySum -gt 0) { [math]::Round($currentSum / $capacitySum, 6) } else { $null }
            가동률 = if ($capacityConstrained -and $capacitySum -gt 0) { [math]::Round($currentSum / $capacitySum, 6) } else { $null }
            가동률해석가능 = $capacityConstrained
            지표해석 = if ($capacityConstrained) { '정원 대비 현원 가동률' } else { '방문형·복지용구는 현원이 이용자수 성격이므로 정원 대비 비율 해석 금지' }
            정원초과행수 = if ($capacityConstrained) { ($knownCurrent | Where-Object { $_.현원 -gt $_.정원 -and $_.정원 -gt 0 }).Count } else { $null }
            자료기준 = '2025-04-01'
            용도 = '2026년 현재값이 아닌 과거 가동률 민감도 기준'
        }
    }
$historicalOccupancySummary |
    Sort-Object 시설_지역코드, 기관유형코드 |
    Export-Csv (Join-Path $analysis 'ltci_historical_occupancy_sigungu_service_type_20250401.csv') -NoTypeInformation -Encoding utf8

Write-Output "region_reference=$($regionReference.Count)"
Write-Output "population_sigungu=$($populationSigungu.Count)"
Write-Output "single_household_sigungu=$($singleSigungu.Count)"
Write-Output "demand_bounds=$($demandBounds.Count)"
Write-Output "supply_region_service=$($supply.Count)"
Write-Output "historical_occupancy_region_service=$($historicalOccupancySummary.Count)"
