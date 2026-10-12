"""Regenerate the committed fund documents.  Run: uv run python -m app.knowledge.build

Markdown goes to app/knowledge/funds (people read it; the local search index is built from it). HTML goes to
app/knowledge/html, which infra/setup_gcp.sh uploads to Cloud Storage for Vertex AI Search to index. Rerun after
refreshing the price history, then rerun the setup step so the index matches.
"""
from pathlib import Path

from app.knowledge.docs import build_all, to_html, to_markdown

HERE = Path(__file__).resolve().parent
MD_DIR = HERE / "funds"
HTML_DIR = HERE / "html"


def main() -> None:
    MD_DIR.mkdir(exist_ok=True)
    HTML_DIR.mkdir(exist_ok=True)
    docs = build_all()
    for doc in docs:
        (MD_DIR / f"{doc.code}.md").write_text(to_markdown(doc), encoding="utf-8", newline="\n")
        (HTML_DIR / f"{doc.code}.html").write_text(to_html(doc), encoding="utf-8", newline="\n")
    print(f"wrote {len(docs)} documents")


if __name__ == "__main__":
    main()
