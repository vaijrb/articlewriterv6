"""
Pydantic models for papers, trends, and pipeline data. Ensures type safety and serialization.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Paper(BaseModel):
    """Single scholarly paper from retrieval."""

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    doi: str | None = None
    year: int | None = None
    journal: str | None = None
    citation_count: int = 0
    source: str = ""  # crossref, semantic_scholar, etc.
    url: str | None = None
    keywords: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_apa_citation(self) -> str:
        """Produce APA 7 in-text style: (Author et al., Year)."""
        if not self.authors:
            return "(n.d.)"
        first = self.authors[0].split()[-1] if self.authors[0] else "Unknown"
        year = self.year or "n.d."
        if len(self.authors) > 1:
            return f"({first} et al., {year})"
        return f"({first}, {year})"


class TrendingTopic(BaseModel):
    """One trending topic from trend detection."""

    topic_id: str | None = None
    label: str
    keywords: list[str] = Field(default_factory=list)
    score: float = 0.0
    paper_count: int = 0
    avg_citations: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrendAnalysisResult(BaseModel):
    """Output of trend detection module."""

    domain: str
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    topics: list[TrendingTopic] = Field(default_factory=list)
    raw_keywords: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SynthesisResult(BaseModel):
    """Output of research synthesis engine."""

    thematic_review: str = ""
    research_gaps: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    methodology_comparison: str = ""
    contradictions: list[str] = Field(default_factory=list)
    papers_used: list[str] = Field(default_factory=list)  # DOIs or titles


class PlagiarismSection(BaseModel):
    """One flagged section in plagiarism report."""

    section_name: str
    similarity_score: float
    source_dois: list[str] = Field(default_factory=list)
    snippet: str = ""
    paraphrased: bool = False


class PlagiarismReport(BaseModel):
    """Full plagiarism check output."""

    overall_risk: str = "low"  # low, medium, high
    max_similarity: float = 0.0
    sections: list[PlagiarismSection] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ArticleSections(BaseModel):
    """Structured sections for the generated article (before final docx)."""

    title: str = ""
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    introduction: str = ""
    literature_review: str = ""
    methodology: str = ""
    results: str = ""
    discussion: str = ""
    theoretical_implications: str = ""
    practical_implications: str = ""
    limitations: str = ""
    future_research: str = ""
    conclusion: str = ""
    references: list[dict[str, str]] = Field(default_factory=list)  # APA entries with doi, etc.
