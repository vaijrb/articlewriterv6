# Module Documentation

## 1. Trend Detection (`trend_detection`)

- **Purpose**: Identify trending topics and research clusters in a defined academic domain.
- **Sources**: CrossRef API, Semantic Scholar API (no paywall scraping).
- **Process**: Query APIs with domain keywords (last 3–5 years) → collect papers → extract text (title + abstract) → TF-IDF vectorization → K-Means clustering → derive topic labels from top terms → rank by score and average citations.
- **Output**: `TrendAnalysisResult` (domain, list of `TrendingTopic` with label, keywords, score, paper_count, avg_citations). Papers are kept for downstream retrieval/synthesis.
- **Config**: `domain.keywords`, `domain.years_back`, `sources.crossref_rpm`, `sources.semantic_scholar_rpm`.

## 2. Scholarly Retrieval (`retrieval`)

- **Purpose**: Fetch and store peer-reviewed papers with full metadata; deduplicate by DOI.
- **Components**:
  - **ScholarlyRetriever**: Queries CrossRef and Semantic Scholar; maps responses to `Paper` model; respects rate limits.
  - **PaperStore**: SQLite persistence; `upsert` by DOI; `get_all`, `get_by_dois`, `export_json`.
- **Output**: List of `Paper` (title, authors, abstract, DOI, year, journal, citation_count, source, url).
- **Config**: `retrieval.max_papers_per_query`, `retrieval.min_citation_count`, `retrieval.deduplicate_by_doi`.

## 3. Research Synthesis (`synthesis`)

- **Purpose**: LLM-based summarization and analysis of retrieved papers.
- **Process**: Truncate abstracts for token limits → single LLM call (OpenAI or Anthropic) with structured prompt → parse JSON for thematic review, methodology comparison, research gaps, contradictions, hypotheses.
- **Output**: `SynthesisResult` (thematic_review, methodology_comparison, research_gaps, contradictions, hypotheses, papers_used).
- **Config**: `synthesis.llm_provider`, `synthesis.max_papers_for_synthesis`, `synthesis.max_tokens_per_call`. Env: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

## 4. Article Generation (`generation`)

- **Purpose**: Produce full APA 7 manuscript using only retrieved papers as sources.
- **Process**: Build references block from papers → LLM prompt with synthesis + references → parse JSON into sections (title, abstract, keywords, introduction, literature review, methodology, results, discussion, implications, limitations, future research, conclusion, references).
- **Constraints**: No hallucinated citations; in-text format (Author et al., Year); target 6,000–8,000 words; abstract 150–250 words.
- **Output**: `ArticleSections` (all section strings + list of reference dicts with apa_string, doi).
- **Config**: `article.target_word_count_min/max`, `article.abstract_word_min/max`, `article.keywords_count`.

## 5. Plagiarism Check (`plagiarism`)

- **Purpose**: Estimate similarity of article sections to source abstracts; flag and optionally paraphrase.
- **Methods**: TF-IDF cosine similarity (section vs. each abstract); character shingles + Jaccard. Section score = max(cosine_max, jaccard_max).
- **Process**: For each section, compute scores → if above threshold and `auto_paraphrase`, call LLM to paraphrase → update section text.
- **Output**: `PlagiarismReport` (overall_risk, max_similarity, list of `PlagiarismSection` with section_name, similarity_score, source_dois, snippet, paraphrased). Updated `ArticleSections` if paraphrasing applied.
- **Config**: `plagiarism.similarity_threshold`, `plagiarism.shingle_size`, `plagiarism.auto_paraphrase_flagged`.

## 6. APA Formatting (`formatting`)

- **Purpose**: Produce submission-ready .docx and .pdf in APA 7 style.
- **Docx**: python-docx — 1" margins, Times New Roman 12pt, double spacing, centered title, optional running head, section headings, first-line and hanging indents, references with hanging indent. Optional academic integrity disclaimer at end.
- **PDF**: Prefer docx2pdf (if installed) from .docx; else reportlab build from sections.
- **Config**: `formatting.font_name`, `font_size`, `margin_inches`, `line_spacing`, `running_head`.

## 7. Output (`outputs`)

- **Purpose**: Write all pipeline artifacts to a single output directory.
- **Files**: article.docx, article.pdf, references.bib, plagiarism_report.json, trends_analysis.json. Bib entries are minimal (note = APA string, doi if available).
- **Config**: `output.dir`, `output.docx_filename`, `output.pdf_filename`, etc.

## 8. Orchestrator (`orchestrator`)

- **Purpose**: Run the full pipeline from config and env.
- **Steps**: `run_trend_detection` → `run_retrieval` → `run_synthesis` → `run_article_generation` → `run_plagiarism_check` → `run_format_and_output`. Each step can be run separately; dependencies (e.g. papers, synthesis) are filled by previous steps.
- **Config**: All sections of `config/default.yaml`; env via `get_env_settings()`.
