"""
Custom exceptions for the pipeline. Enables clear error handling and retries.
"""


class ArticleWriterError(Exception):
    """Base exception for the article writer system."""

    pass


class ConfigError(ArticleWriterError):
    """Invalid or missing configuration."""

    pass


class RetrievalError(ArticleWriterError):
    """Failed to retrieve papers from a source."""

    pass


class SynthesisError(ArticleWriterError):
    """LLM or synthesis step failed."""

    pass


class PlagiarismThresholdExceeded(ArticleWriterError):
    """Similarity above threshold after paraphrase attempts."""

    pass
