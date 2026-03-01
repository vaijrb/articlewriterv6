# Project Improvements Summary

## Code quality and safety

- **Shared utils** (`src/articlewriter/utils.py`): Centralized `rate_limit`, `safe_year_from_crossref`, `bib_escape`, `xml_escape`, `strip_json_code_fence`, and `get_with_retries` to avoid duplication and standardize behavior.
- **Safe year parsing**: CrossRef `date-parts` are parsed with bounds checks (1900–2100); no bare indexing that could raise.
- **SQL safety**: `PaperStore.get_all(order_by)` only allows a fixed allowlist of sort columns (`citation_count DESC`, `year DESC`, etc.); no string interpolation of user input into SQL.
- **BibTeX escaping**: `references.bib` note/doi values are escaped with `bib_escape` so braces and backslashes don’t break entries.
- **Reportlab XML escaping**: Title, body, and reference text in the PDF path are passed through `xml_escape` to avoid broken or unsafe output from `&`, `<`, `>`.

## Resilience and config

- **API retries**: Trend detector and retriever use `get_with_retries()` for HTTP GETs (exponential backoff on 5xx and connection errors; configurable via `ethics.max_retries_per_api` in the future).
- **Config validation**: Empty `domain.keywords` is detected in the orchestrator; defaults to `["machine learning", "research"]` and a warning is logged.
- **Empty retrieval queries**: If no keywords are available, retrieval falls back to `["machine learning", "research"]` with a warning.
- **LLM API key check**: `_ensure_llm_key()` runs before synthesis and article generation and raises `ConfigError` with a clear message if the chosen provider’s API key is missing.

## Observability and types

- **Orchestrator logging**: Structlog is used at step boundaries (trend_detection, retrieval, synthesis, article_generation, plagiarism_check) with relevant context (e.g. paper count, risk level).
- **Type hints**: Pipeline state attributes use explicit types (`TrendAnalysisResult | None`, `PlagiarismReport | None`).

## LLM output handling

- **JSON code fences**: Synthesis and article generation use `strip_json_code_fence()` so markdown-wrapped JSON from the LLM is cleaned before `json.loads()`.

## Suggested next steps

- Wire `ethics.max_retries_per_api` from config into `get_with_retries(max_retries=...)` in detector and retriever.
- Add optional PubMed client with the same retry/rate-limit pattern.
- Add unit tests for `utils` (escape functions, safe_year, strip_json_code_fence) and for storage `get_all` allowlist behavior.
