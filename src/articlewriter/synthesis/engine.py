"""
Research Synthesis Engine: uses an LLM to summarize papers, compare methodologies,
identify gaps and contradictions, and produce thematic review and hypotheses.
"""

import json
from typing import Any

from articlewriter.models import Paper, SynthesisResult
from articlewriter.exceptions import SynthesisError


def _truncate_abstracts(papers: list[Paper], max_chars_per_paper: int = 1500) -> list[dict[str, Any]]:
    """Prepare paper summaries for prompt (avoid token overflow)."""
    out = []
    for i, p in enumerate(papers[:50], 1):
        abstract = (p.abstract or "")[:max_chars_per_paper]
        out.append({
            "num": i,
            "title": p.title[:300],
            "authors": ", ".join(p.authors[:5]) if p.authors else "Unknown",
            "year": p.year,
            "doi": p.doi,
            "abstract": abstract,
        })
    return out


class SynthesisEngine:
    """
    LLM-based synthesis: key findings, methodology comparison, gaps, contradictions,
    thematic review, and hypotheses. Uses OpenAI or Anthropic via env API keys.
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        model: str | None = None,
        max_tokens: int = 4096,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
    ):
        self.llm_provider = llm_provider.lower()
        self.model = model or ("gpt-4o-mini" if self.llm_provider == "openai" else "claude-3-haiku-20240307")
        self.max_tokens = max_tokens
        self._openai_key = openai_api_key
        self._anthropic_key = anthropic_api_key

    def _get_client(self) -> Any:
        if self.llm_provider == "openai":
            try:
                from openai import OpenAI
                return OpenAI(api_key=self._openai_key)
            except Exception as e:
                raise SynthesisError(f"OpenAI client failed: {e}") from e
        if self.llm_provider == "anthropic":
            try:
                from anthropic import Anthropic
                return Anthropic(api_key=self._anthropic_key)
            except Exception as e:
                raise SynthesisError(f"Anthropic client failed: {e}") from e
        raise SynthesisError(f"Unsupported LLM provider: {self.llm_provider}")

    def _call_llm(self, system: str, user: str) -> str:
        """Single LLM call; returns content string."""
        if self.llm_provider == "openai":
            client = self._get_client()
            r = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=self.max_tokens,
            )
            return (r.choices[0].message.content or "").strip()
        if self.llm_provider == "anthropic":
            client = self._get_client()
            m = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return (m.content[0].text if m.content else "").strip()
        return ""

    def run(self, papers: list[Paper], domain: str = "research") -> SynthesisResult:
        """
        Synthesize papers into thematic review, gaps, and hypotheses.
        Uses only retrieved paper data; no hallucinated citations.
        """
        if not papers:
            return SynthesisResult()

        summaries = _truncate_abstracts(papers)
        papers_json = json.dumps(summaries, indent=2, ensure_ascii=False)

        system = """You are an expert academic research synthesizer. Your task is to analyze a set of scholarly paper abstracts and produce a structured synthesis. You must base all statements only on the provided papers; do not add or invent citations. Output valid JSON only, with no markdown code fences."""

        user = f"""Domain: {domain}

Papers (title, authors, year, DOI, abstract excerpt):
{papers_json}

Produce a JSON object with exactly these keys (all strings or arrays of strings):
- "thematic_review": A coherent thematic literature review (about 400-600 words) summarizing main findings and themes across the papers. Use in-text citations as (Author et al., Year) matching the provided papers only.
- "methodology_comparison": A short comparison of methodologies used across the papers (about 150-200 words).
- "research_gaps": Array of 3-6 specific research gaps identified from the literature.
- "contradictions": Array of any methodological or findings contradictions noted (can be empty).
- "hypotheses": Array of 2-5 testable hypotheses or research questions suggested by the gaps.

Return only the JSON object, no other text."""

        try:
            raw = self._call_llm(system, user)
            # Strip markdown code block if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise SynthesisError(f"LLM did not return valid JSON: {e}") from e

        dois = [p.doi for p in papers if p.doi]
        return SynthesisResult(
            thematic_review=data.get("thematic_review", ""),
            methodology_comparison=data.get("methodology_comparison", ""),
            research_gaps=data.get("research_gaps", []),
            contradictions=data.get("contradictions", []),
            hypotheses=data.get("hypotheses", []),
            papers_used=dois[:50],
        )
