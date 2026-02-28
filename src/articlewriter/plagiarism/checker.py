"""
Plagiarism Risk Check: cosine similarity and shingling + Jaccard against source abstracts.
Flags sections above threshold; optional auto-paraphrase via LLM.
"""

import re
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from articlewriter.models import ArticleSections, Paper, PlagiarismReport, PlagiarismSection


def _shingle(text: str, k: int) -> set[str]:
    """Character k-shingles."""
    text = re.sub(r"\s+", " ", text.lower().strip())
    return set(text[i : i + k] for i in range(len(text) - k + 1) if len(text) >= k)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class PlagiarismChecker:
    """
    Compares article sections to source abstracts using TF-IDF cosine similarity
    and character shingles + Jaccard. Optionally paraphrases flagged content.
    """

    def __init__(
        self,
        threshold: float = 0.15,
        shingle_size: int = 5,
        auto_paraphrase: bool = False,
        openai_api_key: str | None = None,
    ):
        self.threshold = threshold
        self.shingle_size = shingle_size
        self.auto_paraphrase = auto_paraphrase
        self._openai_key = openai_api_key

    def _section_texts(self, sections: ArticleSections) -> list[tuple[str, str]]:
        """(section_name, text) for each section with content."""
        out = []
        for name, text in [
            ("abstract", sections.abstract),
            ("introduction", sections.introduction),
            ("literature_review", sections.literature_review),
            ("methodology", sections.methodology),
            ("results", sections.results),
            ("discussion", sections.discussion),
            ("theoretical_implications", sections.theoretical_implications),
            ("practical_implications", sections.practical_implications),
            ("limitations", sections.limitations),
            ("future_research", sections.future_research),
            ("conclusion", sections.conclusion),
        ]:
            if text and text.strip():
                out.append((name, text.strip()))
        return out

    def _similarity_scores(
        self,
        section_text: str,
        source_abstracts: list[str],
    ) -> tuple[float, float]:
        """Returns (cosine_max, jaccard_max) against source abstracts."""
        if not section_text or not source_abstracts:
            return 0.0, 0.0
        # Cosine: TF-IDF on section + all abstracts
        all_docs = [section_text] + source_abstracts
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        X = vec.fit_transform(all_docs)
        sims = cosine_similarity(X[0:1], X[1:])[0]
        cos_max = float(sims.max()) if len(sims) else 0.0
        # Jaccard (shingles) vs each abstract
        sh_a = _shingle(section_text, self.shingle_size)
        jacc_max = 0.0
        for ab in source_abstracts:
            if not ab:
                continue
            j = _jaccard(sh_a, _shingle(ab, self.shingle_size))
            jacc_max = max(jacc_max, j)
        return cos_max, jacc_max

    def _paraphrase(self, text: str) -> str:
        """Simple LLM paraphrase to reduce similarity (OpenAI)."""
        if not self._openai_key:
            return text
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._openai_key)
            r = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Paraphrase the following academic text to preserve meaning but use different wording and sentence structure. Output only the paraphrased text, no quotes or explanation."},
                    {"role": "user", "content": text[:3000]},
                ],
                max_tokens=2048,
            )
            return (r.choices[0].message.content or text).strip()
        except Exception:
            return text

    def run(
        self,
        sections: ArticleSections,
        papers: list[Paper],
    ) -> tuple[PlagiarismReport, ArticleSections]:
        """
        Check each section against paper abstracts. If auto_paraphrase is True,
        paraphrase flagged sections and return updated sections.
        """
        source_abstracts = [p.abstract or "" for p in papers if (p.abstract or "").strip()]
        report_sections: list[PlagiarismSection] = []
        sections_out = ArticleSections(
            title=sections.title,
            abstract=sections.abstract,
            keywords=sections.keywords,
            introduction=sections.introduction,
            literature_review=sections.literature_review,
            methodology=sections.methodology,
            results=sections.results,
            discussion=sections.discussion,
            theoretical_implications=sections.theoretical_implications,
            practical_implications=sections.practical_implications,
            limitations=sections.limitations,
            future_research=sections.future_research,
            conclusion=sections.conclusion,
            references=sections.references,
        )
        max_sim = 0.0

        for name, text in self._section_texts(sections):
            cos_max, jacc_max = self._similarity_scores(text, source_abstracts)
            # Combine: use max of cosine and Jaccard as section score
            score = max(cos_max, jacc_max)
            max_sim = max(max_sim, score)
            flagged = score > self.threshold
            new_text = text
            paraphrased = False
            if flagged and self.auto_paraphrase:
                new_text = self._paraphrase(text)
                paraphrased = True
                if name == "abstract":
                    sections_out.abstract = new_text
                elif name == "introduction":
                    sections_out.introduction = new_text
                elif name == "literature_review":
                    sections_out.literature_review = new_text
                elif name == "methodology":
                    sections_out.methodology = new_text
                elif name == "results":
                    sections_out.results = new_text
                elif name == "discussion":
                    sections_out.discussion = new_text
                elif name == "theoretical_implications":
                    sections_out.theoretical_implications = new_text
                elif name == "practical_implications":
                    sections_out.practical_implications = new_text
                elif name == "limitations":
                    sections_out.limitations = new_text
                elif name == "future_research":
                    sections_out.future_research = new_text
                elif name == "conclusion":
                    sections_out.conclusion = new_text

            report_sections.append(
                PlagiarismSection(
                    section_name=name,
                    similarity_score=round(score, 4),
                    source_dois=[p.doi for p in papers if p.doi][:5],
                    snippet=text[:200] + "..." if len(text) > 200 else text,
                    paraphrased=paraphrased,
                )
            )

        risk = "high" if max_sim > 0.25 else ("medium" if max_sim > self.threshold else "low")
        report = PlagiarismReport(
            overall_risk=risk,
            max_similarity=round(max_sim, 4),
            sections=report_sections,
        )
        return report, sections_out
