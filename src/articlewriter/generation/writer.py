"""
Article Generation Module: generates full academic manuscript in APA 7 structure
(Abstract, Introduction, Literature Review, Methodology, Results, Discussion, etc.)
using only retrieved papers for citations. Target 6,000–8,000 words.
"""

import json
from typing import Any

from articlewriter.models import ArticleSections, Paper, SynthesisResult
from articlewriter.exceptions import SynthesisError
from articlewriter.utils import strip_json_code_fence


def _refs_for_prompt(papers: list[Paper]) -> str:
    """Format papers as reference list for LLM (APA-style lines)."""
    lines = []
    for p in papers[:40]:
        auth = " & ".join(p.authors[:7]) if p.authors else "Unknown"
        year = p.year or "n.d."
        title = p.title
        journal = f" *{p.journal}*" if p.journal else ""
        doi = f" https://doi.org/{p.doi}" if p.doi else ""
        lines.append(f"- {auth} ({year}). {title}.{journal}{doi}")
    return "\n".join(lines)


class ArticleGenerator:
    """
    LLM-based generator for a full APA 7 manuscript. Uses synthesis result and
    stored papers; cites only those papers (no hallucinated refs).
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        model: str | None = None,
        max_tokens: int = 4096,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        target_word_min: int = 6000,
        target_word_max: int = 8000,
        abstract_word_min: int = 150,
        abstract_word_max: int = 250,
        keywords_count: int = 6,
    ):
        self.llm_provider = llm_provider.lower()
        self.model = model or ("gpt-4o" if self.llm_provider == "openai" else "claude-3-sonnet-20240229")
        self.max_tokens = max_tokens
        self._openai_key = openai_api_key
        self._anthropic_key = anthropic_api_key
        self.target_word_min = target_word_min
        self.target_word_max = target_word_max
        self.abstract_word_min = abstract_word_min
        self.abstract_word_max = abstract_word_max
        self.keywords_count = keywords_count

    def _get_client(self) -> Any:
        if self.llm_provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self._openai_key)
        if self.llm_provider == "anthropic":
            from anthropic import Anthropic
            return Anthropic(api_key=self._anthropic_key)
        raise SynthesisError(f"Unsupported LLM provider: {self.llm_provider}")

    def _call_llm(self, system: str, user: str) -> str:
        if self.llm_provider == "openai":
            r = self._get_client().chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=self.max_tokens,
            )
            return (r.choices[0].message.content or "").strip()
        if self.llm_provider == "anthropic":
            m = self._get_client().messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return (m.content[0].text if m.content else "").strip()
        return ""

    def run(
        self,
        synthesis: SynthesisResult,
        papers: list[Paper],
        domain: str = "research",
        article_title: str | None = None,
    ) -> ArticleSections:
        """
        Generate full article sections. All in-text citations must match the provided
        references list (Author et al., Year). No invented DOIs or sources.
        """
        refs_block = _refs_for_prompt(papers)
        word_target = f"{self.target_word_min}-{self.target_word_max} words total (body)"
        abstract_range = f"{self.abstract_word_min}-{self.abstract_word_max} words"

        system = """You are an expert academic writer. Write a journal-ready research article in APA 7th edition style. Use only the references provided; every in-text citation must be (Author et al., Year) or (Author, Year) matching exactly one of the given references. Do not invent any citation or DOI. Use formal scholarly tone, logical transitions, and avoid repetition. Output valid JSON only."""

        user = f"""Domain: {domain}

References (use ONLY these for citations):
{refs_block}

Synthesis inputs:
- Thematic review: {synthesis.thematic_review[:2000]}
- Methodology comparison: {synthesis.methodology_comparison[:800]}
- Research gaps: {synthesis.research_gaps}
- Hypotheses: {synthesis.hypotheses}

Generate a complete manuscript. Target length: {word_target}. Abstract: {abstract_range}. Keywords: {self.keywords_count}.

Return a single JSON object with these exact keys (all strings except keywords and references):
- "title": Article title (concise, descriptive)
- "abstract": Abstract {abstract_range}
- "keywords": Array of {self.keywords_count} keywords
- "introduction": Introduction section (~800-1000 words)
- "literature_review": Literature review (~1200-1500 words), cite provided refs
- "methodology": Methodology (conceptual or empirical) (~800-1000 words)
- "results": Results (simulated if conceptual) (~600-800 words)
- "discussion": Discussion (~800-1000 words)
- "theoretical_implications": Theoretical implications (~300-400 words)
- "practical_implications": Practical implications (~300-400 words)
- "limitations": Limitations (~200-300 words)
- "future_research": Future research (~200-300 words)
- "conclusion": Conclusion (~300-400 words)
- "references": Array of objects with keys: "apa_string" (full APA 7 entry), "doi" (if any)

Use only the references listed above; do not add any new source. Return only the JSON object, no markdown."""

        raw = self._call_llm(system, user)
        raw = strip_json_code_fence(raw)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SynthesisError(f"Article generator did not return valid JSON: {e}") from e

        refs_list = data.get("references", [])
        if not refs_list and papers:
            # Build APA references from papers
            refs_list = []
            for p in papers[:50]:
                auth = " & ".join(p.authors[:7]) if p.authors else "Unknown"
                year = str(p.year) if p.year else "n.d."
                title = p.title + "."
                journal = f" *{p.journal}*" if p.journal else ""
                vol = ""
                doi = f" https://doi.org/{p.doi}" if p.doi else ""
                refs_list.append({"apa_string": f"{auth} ({year}). {title}{journal}{vol}{doi}", "doi": p.doi})

        return ArticleSections(
            title=data.get("title", article_title or "Research Article"),
            abstract=data.get("abstract", ""),
            keywords=data.get("keywords", [])[:self.keywords_count],
            introduction=data.get("introduction", ""),
            literature_review=data.get("literature_review", ""),
            methodology=data.get("methodology", ""),
            results=data.get("results", ""),
            discussion=data.get("discussion", ""),
            theoretical_implications=data.get("theoretical_implications", ""),
            practical_implications=data.get("practical_implications", ""),
            limitations=data.get("limitations", ""),
            future_research=data.get("future_research", ""),
            conclusion=data.get("conclusion", ""),
            references=refs_list,
        )
