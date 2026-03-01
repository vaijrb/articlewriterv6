"""
End-to-end pipeline: trend detection -> retrieval -> synthesis -> article generation
-> plagiarism check -> APA formatting -> output (docx, pdf, bib, reports).
"""

from pathlib import Path
from typing import Any

import structlog

from articlewriter.config import load_config, get_env_settings
from articlewriter.logging_config import configure_logging
from articlewriter.models import (
    ArticleSections,
    Paper,
    PlagiarismReport,
    SynthesisResult,
    TrendAnalysisResult,
)
from articlewriter.trend_detection import TrendDetector
from articlewriter.retrieval import ScholarlyRetriever, PaperStore
from articlewriter.synthesis import SynthesisEngine
from articlewriter.generation import ArticleGenerator
from articlewriter.plagiarism import PlagiarismChecker
from articlewriter.formatting import APAFormatter
from articlewriter.outputs import OutputWriter
from articlewriter.exceptions import ArticleWriterError, ConfigError


class ArticleWriterPipeline:
    """
    Production pipeline: config-driven, modular, with logging and exception handling.
    """

    def __init__(self, config_path: str | Path | None = None):
        self.config = load_config(config_path)
        env = get_env_settings()
        log_cfg = self.config.get("logging", {})
        configure_logging(
            level=log_cfg.get("level", "INFO"),
            log_file=log_cfg.get("file"),
        )
        self._env = env
        self._store: PaperStore | None = None
        self._papers: list[Paper] = []
        self._trends: TrendAnalysisResult | None = None
        self._synthesis: SynthesisResult | None = None
        self._sections: ArticleSections | None = None
        self._plagiarism_report: PlagiarismReport | None = None
        self._validate_config()

    def _domain(self) -> dict[str, Any]:
        return self.config.get("domain", {})

    def _sources(self) -> dict[str, Any]:
        return self.config.get("sources", {})

    def _retrieval(self) -> dict[str, Any]:
        return self.config.get("retrieval", {})

    def _synthesis_cfg(self) -> dict[str, Any]:
        return self.config.get("synthesis", {})

    def _article_cfg(self) -> dict[str, Any]:
        return self.config.get("article", {})

    def _plagiarism_cfg(self) -> dict[str, Any]:
        return self.config.get("plagiarism", {})

    def _formatting_cfg(self) -> dict[str, Any]:
        return self.config.get("formatting", {})

    def _output_cfg(self) -> dict[str, Any]:
        return self.config.get("output", {})

    def _validate_config(self) -> None:
        """Ensure required config (e.g. domain keywords) is present; raise ConfigError or set defaults."""
        domain = self._domain()
        keywords = domain.get("keywords", [])
        if not keywords:
            self.config.setdefault("domain", {})["keywords"] = ["machine learning", "research"]
            structlog.get_logger().warning("domain.keywords empty; using default keywords")

    def _ensure_llm_key(self) -> None:
        """Raise ConfigError if LLM provider is set but API key is missing."""
        syn_cfg = self._synthesis_cfg()
        provider = (syn_cfg.get("llm_provider") or "openai").lower()
        if provider == "openai" and not self._env.openai_api_key:
            raise ConfigError("OPENAI_API_KEY is required for synthesis and article generation (set in .env)")
        if provider == "anthropic" and not self._env.anthropic_api_key:
            raise ConfigError("ANTHROPIC_API_KEY is required when llm_provider=anthropic (set in .env)")

    def run_trend_detection(self):
        """Step 1: Trend detection; populates papers for retrieval."""
        structlog.get_logger().info("run_trend_detection", domain=self._domain().get("name"))
        domain = self._domain()
        keywords = domain.get("keywords") or ["machine learning"]
        years = domain.get("years_back", 5)
        src = self._sources()
        detector = TrendDetector(
            domain_keywords=keywords,
            years_back=years,
            crossref_rpm=src.get("crossref_rpm", 50),
            semantic_scholar_rpm=src.get("semantic_scholar_rpm", 100),
            semantic_scholar_api_key=self._env.semantic_scholar_api_key,
        )
        self._trends = detector.run(domain_name=domain.get("name", "default"))
        self._papers = detector.get_papers()
        structlog.get_logger().info("trend_detection_done", topics=len(self._trends.topics), papers=len(self._papers))
        return self._trends

    def run_retrieval(self, extra_queries: list[str] | None = None):
        """
        Step 2: Optional additional retrieval and storage. If trend detection
        already ran, merge; otherwise search using domain keywords.
        """
        domain = self._domain()
        keywords = domain.get("keywords") or []
        queries = list(keywords)
        if extra_queries:
            queries = list(set(queries) | set(extra_queries))
        if not queries:
            queries = ["machine learning", "research"]
            structlog.get_logger().warning("no_retrieval_queries", using_default=queries)
        structlog.get_logger().info("run_retrieval", queries=len(queries))
        ret_cfg = self._retrieval()
        src = self._sources()
        store = PaperStore(db_path="data/papers.db")
        retriever = ScholarlyRetriever(
            store=store,
            crossref_rpm=src.get("crossref_rpm", 50),
            semantic_scholar_rpm=src.get("semantic_scholar_rpm", 100),
            semantic_scholar_api_key=self._env.semantic_scholar_api_key,
            max_papers_per_query=ret_cfg.get("max_papers_per_query", 50),
            min_citation_count=ret_cfg.get("min_citation_count", 0),
        )
        retriever.search_and_store(queries, deduplicate_by_doi=ret_cfg.get("deduplicate_by_doi", True))
        self._store = store
        # Merge with trend papers: load from store and add any from trend run not in store
        all_papers = store.get_all()
        seen_dois = {p.doi for p in all_papers if p.doi}
        for p in self._papers:
            if p.doi and p.doi not in seen_dois:
                store.upsert(p)
                all_papers.append(p)
                seen_dois.add(p.doi)
        self._papers = store.get_all()
        structlog.get_logger().info("retrieval_done", papers=len(self._papers))
        return self._papers

    def run_synthesis(self):
        """Step 3: Research synthesis from stored papers."""
        self._ensure_llm_key()
        if not self._papers:
            self.run_retrieval()
        structlog.get_logger().info("run_synthesis", papers=len(self._papers))
        syn_cfg = self._synthesis_cfg()
        max_papers = syn_cfg.get("max_papers_for_synthesis", 30)
        engine = SynthesisEngine(
            llm_provider=syn_cfg.get("llm_provider", "openai"),
            max_tokens=syn_cfg.get("max_tokens_per_call", 4096),
            openai_api_key=self._env.openai_api_key,
            anthropic_api_key=self._env.anthropic_api_key,
        )
        papers = self._papers[:max_papers]
        self._synthesis = engine.run(papers, domain=self._domain().get("name", "research"))
        structlog.get_logger().info("synthesis_done")
        return self._synthesis

    def run_article_generation(self, article_title: str | None = None):
        """Step 4: Generate full article sections."""
        self._ensure_llm_key()
        if self._synthesis is None:
            self.run_synthesis()
        structlog.get_logger().info("run_article_generation")
        art_cfg = self._article_cfg()
        gen = ArticleGenerator(
            llm_provider=self._synthesis_cfg().get("llm_provider", "openai"),
            max_tokens=self._synthesis_cfg().get("max_tokens_per_call", 4096),
            openai_api_key=self._env.openai_api_key,
            anthropic_api_key=self._env.anthropic_api_key,
            target_word_min=art_cfg.get("target_word_count_min", 6000),
            target_word_max=art_cfg.get("target_word_count_max", 8000),
            abstract_word_min=art_cfg.get("abstract_word_min", 150),
            abstract_word_max=art_cfg.get("abstract_word_max", 250),
            keywords_count=art_cfg.get("keywords_count", 6),
        )
        self._sections = gen.run(
            self._synthesis,
            self._papers,
            domain=self._domain().get("name", "research"),
            article_title=article_title,
        )
        structlog.get_logger().info("article_generation_done")
        return self._sections

    def run_plagiarism_check(self):
        """Step 5: Plagiarism risk check; optionally paraphrase flagged sections."""
        if self._sections is None:
            self.run_article_generation()
        pl_cfg = self._plagiarism_cfg()
        checker = PlagiarismChecker(
            threshold=pl_cfg.get("similarity_threshold", 0.15),
            shingle_size=pl_cfg.get("shingle_size", 5),
            auto_paraphrase_flagged=pl_cfg.get("auto_paraphrase_flagged", False),
            openai_api_key=self._env.openai_api_key,
        )
        self._plagiarism_report, self._sections = checker.run(self._sections, self._papers)
        structlog.get_logger().info("plagiarism_check_done", risk=self._plagiarism_report.overall_risk)
        return self._plagiarism_report

    def run_format_and_output(self, write_pdf: bool = True) -> dict[str, Path]:
        """Step 6: APA format and write docx, pdf, bib, reports."""
        if self._sections is None:
            self.run_article_generation()
        out_cfg = self._output_cfg()
        fmt_cfg = self._formatting_cfg()
        formatter = APAFormatter(
            font_name=fmt_cfg.get("font_name", "Times New Roman"),
            font_size=fmt_cfg.get("font_size", 12),
            margin_inches=fmt_cfg.get("margin_inches", 1.0),
            line_spacing=fmt_cfg.get("line_spacing", 2.0),
            running_head=fmt_cfg.get("running_head", True),
        )
        ethics = self.config.get("ethics", {})
        writer = OutputWriter(
            output_dir=out_cfg.get("dir", "output"),
            docx_filename=out_cfg.get("docx_filename", "article.docx"),
            pdf_filename=out_cfg.get("pdf_filename", "article.pdf"),
            bib_filename=out_cfg.get("bib_filename", "references.bib"),
            plagiarism_report_filename=out_cfg.get("plagiarism_report", "plagiarism_report.json"),
            trends_report_filename=out_cfg.get("trends_report", "trends_analysis.json"),
            formatter=formatter,
            add_disclaimer=ethics.get("academic_integrity_disclaimer", True),
        )
        return writer.write_all(
            self._sections,
            plagiarism_report=self._plagiarism_report,
            trends_analysis=self._trends,
            write_pdf=write_pdf,
        )

    def run_full(
        self,
        article_title: str | None = None,
        write_pdf: bool = True,
        skip_trends: bool = False,
    ) -> dict[str, Path]:
        """
        Run full pipeline: trends (unless skip_trends) -> retrieval -> synthesis
        -> generation -> plagiarism -> output. Returns paths to output files.
        """
        if not skip_trends:
            self.run_trend_detection()
        self.run_retrieval()
        self.run_synthesis()
        self.run_article_generation(article_title=article_title)
        self.run_plagiarism_check()
        return self.run_format_and_output(write_pdf=write_pdf)
