"""
Writes all pipeline outputs: article.docx, article.pdf, references.bib,
plagiarism_report.json, trends_analysis.json to a configurable output directory.
"""

import json
from pathlib import Path
from typing import Any

from articlewriter.models import (
    ArticleSections,
    PlagiarismReport,
    TrendAnalysisResult,
)
from articlewriter.formatting.apa_docx import APAFormatter


def _apa_to_bib_entry(ref: dict[str, Any], index: int) -> str:
    """Convert one APA-style ref to a minimal BibTeX entry (for references.bib)."""
    apa = ref.get("apa_string", str(ref))
    doi = ref.get("doi", "")
    # Generate a key: first author + year if possible
    key = f"ref{index}"
    lines = [f"@article{{{key},"]
    if doi:
        lines.append(f'  doi = {{{doi}}},')
    lines.append(f'  note = {{{apa}}},')
    lines.append("}")
    return "\n".join(lines)


class OutputWriter:
    """
    Centralized output: docx, pdf, bib, plagiarism_report.json, trends_analysis.json.
    """

    def __init__(
        self,
        output_dir: str | Path = "output",
        docx_filename: str = "article.docx",
        pdf_filename: str = "article.pdf",
        bib_filename: str = "references.bib",
        plagiarism_report_filename: str = "plagiarism_report.json",
        trends_report_filename: str = "trends_analysis.json",
        formatter: APAFormatter | None = None,
        add_disclaimer: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.add_disclaimer = add_disclaimer
        self.docx_filename = docx_filename
        self.pdf_filename = pdf_filename
        self.bib_filename = bib_filename
        self.plagiarism_report_filename = plagiarism_report_filename
        self.trends_report_filename = trends_report_filename
        self.formatter = formatter or APAFormatter()
        if self.formatter and self.add_disclaimer:
            self.formatter.add_disclaimer = True

    def write_all(
        self,
        sections: ArticleSections,
        plagiarism_report: PlagiarismReport | None = None,
        trends_analysis: TrendAnalysisResult | None = None,
        write_pdf: bool = True,
    ) -> dict[str, Path]:
        """
        Write docx, optional pdf, bib, plagiarism_report.json, trends_analysis.json.
        Returns paths to written files.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out: dict[str, Path] = {}

        docx_path = self.output_dir / self.docx_filename
        self.formatter.to_docx(sections, docx_path)
        out["docx"] = docx_path

        if write_pdf:
            pdf_path = self.output_dir / self.pdf_filename
            self.formatter.to_pdf(sections, pdf_path, docx_path=docx_path)
            out["pdf"] = pdf_path

        bib_path = self.output_dir / self.bib_filename
        with open(bib_path, "w", encoding="utf-8") as f:
            for i, ref in enumerate(sections.references, 1):
                f.write(_apa_to_bib_entry(ref if isinstance(ref, dict) else {"apa_string": str(ref), "doi": ""}, i))
                f.write("\n\n")
        out["bib"] = bib_path

        if plagiarism_report is not None:
            report_path = self.output_dir / self.plagiarism_report_filename
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(plagiarism_report.model_dump(), f, indent=2, ensure_ascii=False)
            out["plagiarism_report"] = report_path

        if trends_analysis is not None:
            trends_path = self.output_dir / self.trends_report_filename
            with open(trends_path, "w", encoding="utf-8") as f:
                json.dump(trends_analysis.model_dump(), f, indent=2, ensure_ascii=False)
            out["trends_analysis"] = trends_path

        return out
