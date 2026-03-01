"""
Scholarly Retriever: fetches papers from CrossRef and Semantic Scholar APIs,
enriches with metadata, and stores in PaperStore with DOI deduplication.
"""

import time
from typing import Any

from articlewriter.models import Paper
from articlewriter.retrieval.storage import PaperStore
from articlewriter.exceptions import RetrievalError
from articlewriter.utils import get_with_retries, rate_limit, safe_year_from_crossref


class ScholarlyRetriever:
    """
    Retrieves peer-reviewed papers from CrossRef and Semantic Scholar.
    Stores results in PaperStore; deduplicates by DOI.
    """

    def __init__(
        self,
        store: PaperStore | None = None,
        crossref_rpm: int = 50,
        semantic_scholar_rpm: int = 100,
        semantic_scholar_api_key: str | None = None,
        max_papers_per_query: int = 50,
        min_citation_count: int = 0,
    ):
        self.store = store or PaperStore()
        self.crossref_rpm = crossref_rpm
        self.semantic_scholar_rpm = semantic_scholar_rpm
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self.max_papers_per_query = max_papers_per_query
        self.min_citation_count = min_citation_count

    def _crossref_search(self, query: str) -> list[Paper]:
        url = "https://api.crossref.org/works"
        params = {
            "query": query,
            "rows": self.max_papers_per_query,
            "sort": "cited-count",
            "order": "desc",
            "select": "DOI,title,author,abstract,published,container-title,is-referenced-by-count,reference-count",
        }
        headers = {"User-Agent": "ArticleWriter/1.0 (mailto:research@example.com)"}
        rate_limit(self.crossref_rpm)
        resp = get_with_retries(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
        papers = []
        for item in items:
            authors = [f"{a.get('given','')} {a.get('family','')}".strip() or "Unknown" for a in item.get("author", [])[:15]]
            title = " ".join(item.get("title", [])) or "Untitled"
            abstract = item.get("abstract", "") or ""
            doi = item.get("DOI")
            year = safe_year_from_crossref(item)
            cit = item.get("is-referenced-by-count", item.get("citation-count", 0)) or 0
            if self.min_citation_count and cit < self.min_citation_count:
                continue
            journal = (item.get("container-title") or [""])[0] or None
            papers.append(
                Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    doi=doi,
                    year=year,
                    journal=journal,
                    citation_count=cit,
                    source="crossref",
                    url=f"https://doi.org/{doi}" if doi else None,
                    keywords=[],
                )
            )
        return papers

    def _semantic_scholar_search(self, query: str) -> list[Paper]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": min(self.max_papers_per_query, 100),
            "fields": "title,authors,abstract,year,citationCount,externalIds,url",
        }
        headers = {"Accept": "application/json"}
        if self.semantic_scholar_api_key:
            headers["x-api-key"] = self.semantic_scholar_api_key
        rate_limit(self.semantic_scholar_rpm)
        resp = get_with_retries(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 429:
            time.sleep(60)
            resp = get_with_retries(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", []) or []
        papers = []
        for item in data:
            cit = item.get("citationCount", 0) or 0
            if self.min_citation_count and cit < self.min_citation_count:
                continue
            ext = item.get("externalIds", {}) or {}
            doi = ext.get("DOI")
            papers.append(
                Paper(
                    title=item.get("title", "Untitled"),
                    authors=[a.get("name", "Unknown") for a in item.get("authors", [])[:15]],
                    abstract=item.get("abstract", "") or "",
                    doi=doi,
                    year=item.get("year"),
                    journal=None,
                    citation_count=cit,
                    source="semantic_scholar",
                    url=item.get("url"),
                    keywords=[],
                )
            )
        return papers

    def search_and_store(
        self,
        queries: list[str],
        deduplicate_by_doi: bool = True,
    ) -> list[Paper]:
        """
        Run search for each query against both APIs, merge, dedupe, and store.
        Returns list of stored papers.
        """
        all_papers: list[Paper] = []
        seen: set[str] = set()

        for q in queries:
            try:
                for p in self._crossref_search(q):
                    key = (p.doi or p.title).lower().strip()
                    if key and key not in seen:
                        seen.add(key)
                        all_papers.append(p)
            except Exception as e:
                raise RetrievalError(f"CrossRef search failed: {e}") from e
            try:
                for p in self._semantic_scholar_search(q):
                    key = (p.doi or p.title).lower().strip()
                    if key and key not in seen:
                        seen.add(key)
                        all_papers.append(p)
            except Exception as e:
                raise RetrievalError(f"Semantic Scholar search failed: {e}") from e

        count = self.store.upsert_many(all_papers, deduplicate_by_doi=deduplicate_by_doi)
        return self.store.get_all()
