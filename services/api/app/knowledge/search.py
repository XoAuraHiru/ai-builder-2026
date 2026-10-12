"""Fund-document retrieval. Vertex AI Search in production; a small keyword index over the same documents locally, in
tests, and whenever Vertex AI Search cannot answer. Either way, results are passages with stable ids ("ATR-BAL#fees")
that AI answers must cite, and the result says which retriever served it.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.knowledge.docs import slug

log = logging.getLogger(__name__)
DOCS_DIR = Path(__file__).resolve().parent / "funds"
STOP = {"the", "and", "for", "with", "that", "this", "are", "was", "its", "from", "you", "your", "has", "have", "not",
        "but", "can", "any", "per", "what", "how", "does", "into", "than", "about", "which", "their", "they", "them",
        "there", "been", "will", "would", "could", "should", "atrium"}


@dataclass(frozen=True)
class Passage:
    id: str
    fund_code: str
    title: str
    text: str


@dataclass
class SearchHits:
    passages: list[Passage]
    retriever: str


class FundSearchError(Exception):
    pass


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3 and t not in STOP]


def parse_markdown(code: str, text: str) -> list[Passage]:
    title = text.splitlines()[0].lstrip("# ").strip()
    out = []
    for block in text.split("\n## ")[1:]:
        heading, _, body = block.partition("\n")
        out.append(Passage(id=f"{code}#{slug(heading)}", fund_code=code, title=f"{title}: {heading.strip()}",
                           text=body.strip()))
    return out


@lru_cache(maxsize=1)
def load_passages() -> tuple[Passage, ...]:
    out: list[Passage] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        out += parse_markdown(path.stem, path.read_text(encoding="utf-8"))
    return tuple(out)


class LocalFundSearch:
    name = "local-index"

    def __init__(self, passages: tuple[Passage, ...] | None = None):
        self.passages = list(passages or load_passages())
        self._counts = [Counter(tokens(f"{p.title} {p.text}")) for p in self.passages]
        df = Counter(t for counts in self._counts for t in counts)
        self._idf = {t: math.log(1 + len(self.passages) / (1 + d)) for t, d in df.items()}

    def _score(self, i: int, terms: set[str]) -> float:
        counts = self._counts[i]
        return sum(counts[t] / (counts[t] + 1.2) * self._idf.get(t, 0.0) for t in terms)

    def search(self, query: str, fund_codes: list[str] | None = None, k: int = 4) -> SearchHits:
        terms = set(tokens(query))
        pool = [i for i, p in enumerate(self.passages) if not fund_codes or p.fund_code in fund_codes]
        scores = {i: self._score(i, terms) for i in pool}
        ranked = sorted(pool, key=lambda i: (-scores[i], i))
        hits = [self.passages[i] for i in ranked if scores[i] > 0][:k]
        return SearchHits(hits or [self.passages[i] for i in pool[:k]], self.name)

    def match(self, code: str, text: str) -> Passage:
        """The document section a search chunk came from, so citations stay stable whichever retriever served them."""
        words = set(tokens(text))
        best, best_score = None, 0.0
        for i, p in enumerate(self.passages):
            if p.fund_code != code or not words:
                continue
            score = len(words & set(self._counts[i])) / len(words)
            if score > best_score:
                best, best_score = p, score
        if best is not None and best_score >= 0.6:
            return best
        title = next((p.title.split(":")[0] for p in self.passages if p.fund_code == code), code)
        return Passage(id=f"{code}#search", fund_code=code, title=f"{title}: search result", text=text.strip()[:1500])


class VertexFundSearch:
    """Vertex AI Search (Discovery Engine) over the fund HTML documents, returning layout-aware chunks."""

    name = "vertex-ai-search"

    def __init__(self, project: str, engine: str, location: str = "global", local: LocalFundSearch | None = None,
                 session=None):
        self.project = project
        self.url = (f"https://discoveryengine.googleapis.com/v1/projects/{project}/locations/{location}/collections/"
                    f"default_collection/engines/{engine}/servingConfigs/default_search:search")
        self.local = local or LocalFundSearch()
        self._session = session

    def _authorized(self):
        if self._session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            self._session = AuthorizedSession(credentials)
        return self._session

    def search(self, query: str, fund_codes: list[str] | None = None, k: int = 4) -> SearchHits:
        body = {"query": query[:500], "pageSize": 10,
                "contentSearchSpec": {"searchResultMode": "CHUNKS",
                                      "chunkSpec": {"numPreviousChunks": 0, "numNextChunks": 0}}}
        try:
            response = self._authorized().post(self.url, json=body, headers={"X-Goog-User-Project": self.project},
                                               timeout=15)
            response.raise_for_status()
            results = response.json().get("results", [])
        except Exception as e:  # network, auth or API errors all mean "use the local index"
            raise FundSearchError(f"Vertex AI Search failed: {e}") from e
        out: list[Passage] = []
        for result in results:
            chunk = result.get("chunk") or {}
            uri = (chunk.get("documentMetadata") or {}).get("uri", "")
            code = uri.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if not code or (fund_codes and code not in fund_codes):
                continue
            content = chunk.get("content", "")
            # Layout chunks keep their headings ("## Fees"), so a chunk maps exactly to the sections it contains.
            known = {p.id: p for p in self.local.passages if p.fund_code == code}
            sections = [known[f"{code}#{slug(h)}"] for h in re.findall(r"(?m)^## (.+)$", content) if f"{code}#{slug(h)}" in known]
            for passage in sections or [self.local.match(code, content)]:
                if passage not in out and len(out) < k:
                    out.append(passage)
            if len(out) == k:
                break
        return SearchHits(out, self.name)


class ResilientFundSearch:
    def __init__(self, primary: VertexFundSearch, backup: LocalFundSearch):
        self.primary, self.backup = primary, backup

    def search(self, query: str, fund_codes: list[str] | None = None, k: int = 4) -> SearchHits:
        try:
            hits = self.primary.search(query, fund_codes, k)
            if hits.passages:
                return hits
            fallback = self.backup.search(query, fund_codes, k)
            return SearchHits(fallback.passages, "local-index (Vertex AI Search found nothing)")
        except FundSearchError as e:
            log.warning("%s; answering from the local index", e)
            fallback = self.backup.search(query, fund_codes, k)
            return SearchHits(fallback.passages, "local-index (Vertex AI Search unavailable)")


_search: LocalFundSearch | ResilientFundSearch | None = None


def get_fund_search():
    """FastAPI dependency: Vertex AI Search when an engine is configured, else the local index."""
    global _search
    if _search is None:
        settings = get_settings()
        local = LocalFundSearch()
        if settings.fund_search_engine and settings.gcp_project:
            _search = ResilientFundSearch(VertexFundSearch(settings.gcp_project, settings.fund_search_engine,
                                                           settings.fund_search_location, local), local)
        else:
            _search = local
    return _search
