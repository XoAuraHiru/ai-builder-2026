from app.knowledge.build import HTML_DIR, MD_DIR
from app.knowledge.docs import build_all, fund_facts, to_html, to_markdown
from app.knowledge.search import (FundSearchError, LocalFundSearch, ResilientFundSearch, VertexFundSearch,
                                  load_passages)
from app.seed.funds import HOUSE_FUNDS, house_fund_objects

SECTION_IDS = ("objective", "what-it-holds", "who-it-suits", "fees", "how-it-behaved", "risks", "important-information")


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.error:
            raise self.error
        return FakeResponse(self.payload)


def test_facts_come_from_real_history():
    facts = fund_facts(house_fund_objects()["ATR-BAL"])
    assert facts["worst_year"]["year"] == 2008 and facts["worst_year"]["return_pct"] < -15
    assert any(c["year"] == 2022 and c["return_pct"] < 0 for c in facts["calendar_years"])
    assert facts["fees"]["atrium_pct"] == 0.35 and facts["fees"]["total_pct"] == 0.38
    assert facts["growth_of_10k"][0]["value"] > 0 and facts["window_start"].startswith("2007")


def test_committed_documents_match_a_fresh_build():
    docs = build_all()
    assert len(docs) == len(HOUSE_FUNDS) + 1
    for doc in docs:
        assert (MD_DIR / f"{doc.code}.md").read_text(encoding="utf-8") == to_markdown(doc), doc.code
        assert (HTML_DIR / f"{doc.code}.html").read_text(encoding="utf-8") == to_html(doc), doc.code


def test_every_fund_has_the_same_sections_and_ids_are_unique():
    ids = [p.id for p in load_passages()]
    assert len(ids) == len(set(ids))
    for spec in HOUSE_FUNDS:
        assert {f"{spec['code']}#{s}" for s in SECTION_IDS} <= set(ids)
    assert "ATRIUM#clear-fees" in ids


def test_local_search_ranks_the_matching_section_first():
    hits = LocalFundSearch().search("what are the fees", ["ATR-BAL"])
    assert hits.passages[0].id == "ATR-BAL#fees" and hits.retriever == "local-index"


def test_vertex_chunks_map_back_to_document_sections():
    local = LocalFundSearch()
    risks = next(p for p in local.passages if p.id == "ATR-TEC#risks")
    session = FakeSession({"results": [
        {"chunk": {"content": "Atrium Technology\nRisks\n" + risks.text,
                   "documentMetadata": {"uri": "gs://bucket/funds/ATR-TEC.html", "title": "ATR-TEC"}}},
        {"chunk": {"content": "Unrelated text", "documentMetadata": {"uri": "gs://bucket/funds/ATR-BAL.html"}}}]})
    hits = VertexFundSearch("proj", "eng", local=local, session=session).search("technology risk", ["ATR-TEC"])
    assert [p.id for p in hits.passages] == ["ATR-TEC#risks"] and hits.retriever == "vertex-ai-search"
    call = session.calls[0]
    assert call["url"].endswith("/engines/eng/servingConfigs/default_search:search")
    assert call["json"]["contentSearchSpec"]["searchResultMode"] == "CHUNKS"
    assert call["headers"]["X-Goog-User-Project"] == "proj"


def test_vertex_errors_are_raised_as_search_errors():
    search = VertexFundSearch("p", "e", session=FakeSession(error=RuntimeError("boom")))
    try:
        search.search("fees")
    except FundSearchError as e:
        assert "boom" in str(e)
    else:
        raise AssertionError("expected FundSearchError")


def test_search_falls_back_to_the_local_index_when_vertex_fails():
    local = LocalFundSearch()
    search = ResilientFundSearch(VertexFundSearch("p", "e", local=local, session=FakeSession(error=RuntimeError("503"))),
                                 local)
    hits = search.search("fees", ["ATR-BAL"])
    assert hits.passages[0].id == "ATR-BAL#fees" and "unavailable" in hits.retriever


def test_a_chunk_spanning_sections_maps_to_each_section_it_contains():
    local = LocalFundSearch()
    content = ("# Atrium Technology (ATR-TEC)\n\n## Objective\n\nConcentrated growth from the US technology sector.\n\n"
               "## What it holds\n\nAtrium Technology holds 2 exchange-traded funds")
    session = FakeSession({"results": [{"chunk": {"content": content, "documentMetadata": {"uri": "gs://b/funds/ATR-TEC.html"}}}]})
    hits = VertexFundSearch("p", "e", local=local, session=session).search("technology", ["ATR-TEC"])
    assert [p.id for p in hits.passages] == ["ATR-TEC#objective", "ATR-TEC#what-it-holds"]
