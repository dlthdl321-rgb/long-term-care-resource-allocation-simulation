"""선행연구 PDF에서 지표·산식 관련 문맥을 추출한다."""

from pathlib import Path

from pypdf import PdfReader


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = REPOSITORY_ROOT / "05_선행연구자료"
OUTPUT = REPOSITORY_ROOT / "03_데이터" / "outputs" / "literature_indicator_context.txt"
KEYWORDS = (
    "비형평",
    "계산식",
    "산식",
    "충족률",
    "충족도",
    "방문요양",
    "방문간호",
    "주야간",
    "농촌",
    "독거",
    "인력",
)


def main() -> None:
    sections: list[str] = []
    for path in sorted(PDF_DIR.glob("*.pdf")):
        reader = PdfReader(path)
        sections.append(f"\n===== {path.name} | {len(reader.pages)}쪽 =====")
        for page_number, page in enumerate(reader.pages, start=1):
            text = " ".join((page.extract_text() or "").split())
            if any(keyword in text for keyword in KEYWORDS):
                sections.append(f"\n[p.{page_number}] {text}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(sections), encoding="utf-8")
    print(f"{len(list(PDF_DIR.glob('*.pdf')))}개 PDF → {OUTPUT}")


if __name__ == "__main__":
    main()
