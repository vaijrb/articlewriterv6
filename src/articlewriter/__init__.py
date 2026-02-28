"""
Journal Article Writer - Automated scholarly article generation system.
Production-ready, modular pipeline: trends -> retrieval -> synthesis -> generation -> plagiarism -> APA output.
"""

__version__ = "1.0.0"

from articlewriter.config import load_config
from articlewriter.orchestrator import ArticleWriterPipeline

__all__ = ["ArticleWriterPipeline", "load_config", "__version__"]
