"""
Scholarly Retrieval Module: fetches papers from CrossRef and Semantic Scholar,
stores in SQLite/JSON, deduplicates by DOI.
"""

from articlewriter.retrieval.retriever import ScholarlyRetriever
from articlewriter.retrieval.storage import PaperStore

__all__ = ["ScholarlyRetriever", "PaperStore"]
