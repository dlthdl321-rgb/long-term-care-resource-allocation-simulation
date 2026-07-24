"""저장소의 공통 경로 정의.

모든 Python 스크립트가 실행 위치와 관계없이 같은 데이터·결과 폴더를
사용하도록 경로를 한곳에서 관리한다.
"""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPOSITORY_ROOT / "03_데이터"
DATA_DIR = WORKSPACE / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ANALYSIS_READY_DIR = DATA_DIR / "analysis_ready"
OUTPUTS_DIR = WORKSPACE / "outputs"
CONFIG_DIR = WORKSPACE / "config"
METADATA_DIR = WORKSPACE / "metadata"
REPORTS_DIR = REPOSITORY_ROOT / "02_분석보고서"
REFERENCES_DIR = REPOSITORY_ROOT / "05_선행연구자료"
