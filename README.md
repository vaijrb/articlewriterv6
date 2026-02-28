# Journal Article Writer

Production-ready, modular Python system that automatically generates a **journal-ready research article** in APA 7th edition by: scanning research trends → retrieving peer-reviewed papers → synthesizing findings → generating an original manuscript → checking plagiarism risk → formatting and outputting .docx, .pdf, and reports.

## Features

- **Trend Detection**: CrossRef + Semantic Scholar APIs; TF-IDF + K-Means clustering for trending topics
- **Scholarly Retrieval**: Structured storage (SQLite), DOI deduplication, metadata (title, authors, abstract, DOI, year, journal, citation count)
- **Research Synthesis**: LLM-based thematic review, methodology comparison, research gaps, hypotheses (OpenAI/Anthropic)
- **Article Generation**: Full APA 7 structure (Abstract, Introduction, Literature Review, Methodology, Results, Discussion, Implications, Limitations, Future Research, Conclusion, References); 6,000–8,000 words; citations only from retrieved papers
- **Plagiarism Check**: Cosine similarity + shingling/Jaccard vs source abstracts; configurable threshold; optional auto-paraphrase
- **APA 7 Formatting**: python-docx (double spacing, 1" margins, Times New Roman 12pt, running head, hanging indents); reportlab for PDF
- **Outputs**: `article.docx`, `article.pdf`, `references.bib`, `plagiarism_report.json`, `trends_analysis.json`

## Requirements

- Python 3.10+
- API keys: **OpenAI** (required for synthesis/generation); optional: Anthropic, Semantic Scholar

## Installation

```bash
git clone <repo>
cd articlewriter
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
pip install -e .   # optional: install package for CLI entry point (articlewriter run)
# Verify: python -c "from articlewriter import ArticleWriterPipeline; print('OK')"
# (Run from project root with PYTHONPATH=src if not installed.)
```

## API Keys

1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY=sk-...` (required for synthesis and article generation).
3. Optional: `SEMANTIC_SCHOLAR_API_KEY` (higher rate limit), `ANTHROPIC_API_KEY` (alternative LLM).

## Configuration

- **Config file**: `config/default.yaml` (domain keywords, years back, rate limits, thresholds, output paths).
- Override path via env: `ARTICLEWRITER_CONFIG=config/custom.yaml`.

## Usage

### Full pipeline (script)

```bash
python scripts/run_pipeline.py
python scripts/run_pipeline.py --skip-trends --no-pdf
python scripts/run_pipeline.py --config config/custom.yaml --title "My Article Title"
```

### CLI (Typer)

```bash
python -m articlewriter.cli run
python -m articlewriter.cli run --skip-trends --no-pdf -t "Custom Title"
python -m articlewriter.cli trends
```

### Streamlit UI

```bash
streamlit run app_streamlit.py
```

### Docker

```bash
docker build -t articlewriter .
docker run -p 8501:8501 --env-file .env -v $(pwd)/output:/app/output articlewriter
```

## Project Structure

```
articlewriter/
├── config/
│   └── default.yaml          # Domain, APIs, thresholds, output paths
├── src/articlewriter/
│   ├── __init__.py
│   ├── config.py              # Config loader, env settings
│   ├── logging_config.py
│   ├── models.py              # Pydantic: Paper, TrendAnalysisResult, SynthesisResult, etc.
│   ├── exceptions.py
│   ├── orchestrator.py        # ArticleWriterPipeline
│   ├── trend_detection/       # TrendDetector (APIs + TF-IDF clustering)
│   ├── retrieval/             # ScholarlyRetriever, PaperStore (SQLite)
│   ├── synthesis/             # SynthesisEngine (LLM)
│   ├── generation/            # ArticleGenerator (LLM, APA structure)
│   ├── plagiarism/            # PlagiarismChecker (cosine + Jaccard, optional paraphrase)
│   ├── formatting/            # APAFormatter (docx, PDF)
│   ├── outputs/               # OutputWriter (docx, pdf, bib, JSON reports)
│   └── cli.py                 # Typer CLI
├── scripts/
│   └── run_pipeline.py
├── app_streamlit.py           # Streamlit UI
├── requirements.txt
├── .env.example
├── Dockerfile
└── README.md
```

## Module Overview

| Module | Role |
|--------|------|
| **Trend Detection** | Fetches papers from CrossRef + Semantic Scholar; clusters with TF-IDF + K-Means; outputs ranked trending topics. |
| **Scholarly Retrieval** | Search and store papers; SQLite + JSON; dedupe by DOI. |
| **Synthesis** | LLM summarizes papers → thematic review, gaps, contradictions, hypotheses. |
| **Article Generation** | LLM produces full manuscript; only retrieved refs cited. |
| **Plagiarism Check** | Similarity vs source abstracts; flag > threshold; optional paraphrase. |
| **APA Formatting** | .docx (double space, margins, TNR 12pt, running head, hanging refs); .pdf via reportlab or docx2pdf. |
| **Output** | Writes article.docx, article.pdf, references.bib, plagiarism_report.json, trends_analysis.json. |

## Ethical Use

- Respect API usage policies (rate limits in config).
- Do not scrape paywalled content.
- System includes an academic integrity disclaimer option in config.
- Use only for legitimate research support; verify all outputs before submission.

## License

Use and modify as needed for your project.
