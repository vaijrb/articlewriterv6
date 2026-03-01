"""
Trend Detection Module: fetches recent papers from CrossRef and Semantic Scholar,
extracts keywords, and clusters them (TF-IDF + clustering). Outputs ranked trending topics.
"""

import time
from typing import Any

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from articlewriter.models import Paper, TrendingTopic, TrendAnalysisResult
from articlewriter.exceptions import RetrievalError
from articlewriter.utils import get_with_retries, rate_limit, safe_year_from_crossref


class TrendDetector:
    """
    Scans scholarly APIs for recent papers, extracts terms, and produces
    ranked trending topics with metadata.
    """

    def __init__(
        self,
        domain_keywords: list[str],
        years_back: int = 5,
        crossref_rpm: int = 50,
        semantic_scholar_rpm: int = 100,
        semantic_scholar_api_key: str | None = None,
    ):
        self.domain_keywords = domain_keywords
        self.years_back = years_back
        self.crossref_rpm = crossref_rpm
        self.semantic_scholar_rpm = semantic_scholar_rpm
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self._papers: list[Paper] = []

    def _fetch_crossref(self, query: str, rows: int = 100) -> list[dict[str, Any]]:
        """Query CrossRef API (no key required; use polite User-Agent)."""
        url = "https://api.crossref.org/works"
        params = {
            "query": query,
            "rows": min(rows, 1000),
            "sort": "cited-count",
            "order": "desc",
            "filter": f"from-pub-date:{self.years_back}-01-01",
        }
        headers = {
            "User-Agent": "ArticleWriter/1.0 (mailto:research@example.com; scholarly use)",
        }
        rate_limit(self.crossref_rpm)
        resp = get_with_retries(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("items", [])

    def _fetch_semantic_scholar(self, query: str, limit: int = 100) -> list[dict[str, Any]]:
        """Query Semantic Scholar API (optional API key for higher rate limit)."""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {"query": query, "limit": min(limit, 100), "fields": "title,authors,abstract,year,citationCount,externalIds,url"}
        headers = {"Accept": "application/json"}
        if self.semantic_scholar_api_key:
            headers["x-api-key"] = self.semantic_scholar_api_key
        rate_limit(self.semantic_scholar_rpm)
        resp = get_with_retries(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 429:
            time.sleep(60)
            resp = get_with_retries(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", []) or []

    def _paper_from_crossref(self, item: dict[str, Any]) -> Paper:
        author_list = []
        for a in item.get("author", [])[:10]:
            name = a.get("given", "") + " " + a.get("family", "")
            author_list.append(name.strip() or "Unknown")
        title = " ".join(item.get("title", [])) or "Untitled"
        abstract = item.get("abstract", "") or ""
        year = safe_year_from_crossref(item)
        doi = item.get("DOI")
        return Paper(
            title=title,
            authors=author_list,
            abstract=abstract,
            doi=doi,
            year=year,
            journal=item.get("container-title", [""])[0] or None,
            citation_count=item.get("is-referenced-by-count", item.get("citation-count", 0)) or 0,
            source="crossref",
            url=f"https://doi.org/{doi}" if doi else None,
            keywords=[],
        )

    def _paper_from_semantic_scholar(self, item: dict[str, Any]) -> Paper:
        authors = [a.get("name", "Unknown") for a in item.get("authors", [])[:10]]
        ext = item.get("externalIds", {}) or {}
        doi = ext.get("DOI")
        return Paper(
            title=item.get("title", "Untitled"),
            authors=authors,
            abstract=item.get("abstract", "") or "",
            doi=doi,
            year=item.get("year"),
            journal=None,
            citation_count=item.get("citationCount", 0) or 0,
            source="semantic_scholar",
            url=item.get("url"),
            keywords=[],
        )

    def fetch_papers(self) -> list[Paper]:
        """Fetch papers from CrossRef and Semantic Scholar for domain keywords; dedupe by DOI."""
        seen_dois: set[str] = set()
        papers: list[Paper] = []

        for kw in self.domain_keywords[:5]:
            try:
                for raw in self._fetch_crossref(kw, rows=50):
                    p = self._paper_from_crossref(raw)
                    key = (p.doi or p.title).lower()
                    if key and key not in seen_dois:
                        seen_dois.add(key)
                        papers.append(p)
            except Exception as e:
                raise RetrievalError(f"CrossRef fetch failed for '{kw}': {e}") from e

            try:
                for raw in self._fetch_semantic_scholar(kw, limit=30):
                    p = self._paper_from_semantic_scholar(raw)
                    key = (p.doi or p.title).lower()
                    if key and key not in seen_dois:
                        seen_dois.add(key)
                        papers.append(p)
            except Exception as e:
                raise RetrievalError(f"Semantic Scholar fetch failed for '{kw}': {e}") from e

        self._papers = papers
        return papers

    def _extract_text_for_clustering(self) -> list[str]:
        """Combine title + abstract for each paper for TF-IDF."""
        return [f"{p.title} {p.abstract}" for p in self._papers if p.title or p.abstract]

    def _cluster_keywords(self, n_topics: int = 8) -> list[TrendingTopic]:
        """Use TF-IDF + KMeans to cluster papers; derive topic labels from top terms."""
        if not self._papers:
            return []

        texts = self._extract_text_for_clustering()
        if len(texts) < 3:
            # Too few for clustering; single topic from domain keywords
            return [
                TrendingTopic(
                    label="General domain",
                    keywords=self.domain_keywords[:5],
                    score=1.0,
                    paper_count=len(self._papers),
                    avg_citations=sum(p.citation_count for p in self._papers) / max(len(self._papers), 1),
                )
            ]

        vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=2,
        )
        X = vectorizer.fit_transform(texts)
        n_clusters = min(n_topics, max(2, len(self._papers) // 5))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)
        feature_names = vectorizer.get_feature_names_out()

        topics: list[TrendingTopic] = []
        for c in range(n_clusters):
            center = kmeans.cluster_centers_[c]
            top_idx = center.argsort()[-10:][::-1]
            topic_keywords = [feature_names[i] for i in top_idx if center[i] > 0]
            cluster_papers = [self._papers[i] for i in range(len(self._papers)) if labels[i] == c]
            avg_cit = sum(p.citation_count for p in cluster_papers) / max(len(cluster_papers), 1)
            # Score: combination of cluster size and avg citations (normalized)
            score = len(cluster_papers) / max(len(self._papers), 1) + 0.3 * min(avg_cit / 100, 1.0)
            label = topic_keywords[0].replace("_", " ").title() if topic_keywords else f"Cluster {c+1}"
            topics.append(
                TrendingTopic(
                    topic_id=f"topic_{c}",
                    label=label,
                    keywords=topic_keywords[:7],
                    score=round(score, 4),
                    paper_count=len(cluster_papers),
                    avg_citations=round(avg_cit, 1),
                    metadata={"cluster_id": c},
                )
            )

        topics.sort(key=lambda t: (t.score, t.avg_citations), reverse=True)
        return topics

    def run(self, domain_name: str = "default") -> TrendAnalysisResult:
        """Fetch papers, cluster, and return ranked trending topics."""
        self.fetch_papers()
        topics = self._cluster_keywords()
        return TrendAnalysisResult(
            domain=domain_name,
            topics=topics,
            raw_keywords=self.domain_keywords,
            metadata={"total_papers": len(self._papers)},
        )

    def get_papers(self) -> list[Paper]:
        """Return papers collected during last run (for downstream retrieval/synthesis)."""
        return self._papers
