# 한국사회보장정보원 사회복지시설 목록 수집 기록

- 데이터명: 한국사회보장정보원_사회복지시설정보서비스 현황
- 데이터 ID: 15001848
- 공식 출처: https://www.data.go.kr/data/15001848/openapi.do
- 수집일: 2026-07-23
- API 총건수: 30,558
- 고유 시설코드: 30,558
- 시설유형 코드: 101종
- 노인 분야 코드(`01` 시작): 16,956개
- 분석용 CSV SHA-256: `DA920466D7719154E200B2B3F67FEBC6EC9527F87CA4799E27D99B3ADC7323D6`

## 저장 파일

- 페이지별 원본 XML 31개: `data/raw/social_welfare_facilities_xml/`
- 분석용 목록: `data/processed/social_welfare_facility_list_20260723.csv`
- 재수집 스크립트: `scripts/collect_social_welfare_facility_list.ps1`

## 주요 컬럼

`facility_code`, `facility_name`, `facility_type_code`, `facility_type_name`, `certification_flag`, `facility_status_code`

## 활용 범위와 주의사항

- 재가노인복지시설 9,701개, 노인의료복지시설 6,172개 등 장기요양기관 외 사회복지시설 유형을 확인할 수 있다.
- 목록 API의 모든 응답은 상태코드 `1`이지만 이것만으로 실제 서비스 운영·잔여역량을 단정하지 않는다.
- 이 API 기능은 주소와 시군구를 반환하지 않는다. 따라서 전국 시설유형 총량과 기존 장기요양기관 목록의 누락 점검에 사용하고, 지역별 공급량으로 직접 사용하지 않는다.
- 주소가 필요한 시설은 시설별 기본정보 API 또는 전국사회복지시설표준데이터의 별도 상세 기능이 필요하다.
- 인증키는 원본·CSV·스크립트 어디에도 저장하지 않았다.
