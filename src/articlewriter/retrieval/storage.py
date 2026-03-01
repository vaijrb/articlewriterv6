"""
Structured storage for papers: SQLite with optional JSON export. Deduplication by DOI.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

from articlewriter.models import Paper


class PaperStore:
    """
    Persist and query papers. Uses SQLite; deduplicates by DOI.
    """

    def __init__(self, db_path: str | Path = "data/papers.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    doi TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    authors_json TEXT,
                    abstract TEXT,
                    year INTEGER,
                    journal TEXT,
                    citation_count INTEGER DEFAULT 0,
                    source TEXT,
                    url TEXT,
                    keywords_json TEXT,
                    extra_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_papers_citations ON papers(citation_count)"
            )

    def _paper_to_row(self, p: Paper) -> tuple[Any, ...]:
        doi = p.doi or p.title[:200]  # fallback key if no DOI
        return (
            doi,
            p.title,
            json.dumps(p.authors),
            p.abstract or "",
            p.year,
            p.journal or "",
            p.citation_count,
            p.source or "",
            p.url or "",
            json.dumps(p.keywords),
            json.dumps(p.extra),
        )

    def _row_to_paper(self, row: tuple[Any, ...]) -> Paper:
        return Paper(
            title=row[1],
            authors=json.loads(row[2] or "[]"),
            abstract=row[3] or "",
            doi=row[0] if row[0] and row[0].startswith("10.") else row[0],
            year=row[4],
            journal=row[5] or None,
            citation_count=row[6] or 0,
            source=row[7] or "",
            url=row[8] or None,
            keywords=json.loads(row[9] or "[]"),
            extra=json.loads(row[10] or "{}"),
        )

    def upsert(self, paper: Paper) -> bool:
        """Insert or replace by DOI (or title fallback). Returns True if inserted."""
        row = self._paper_to_row(paper)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO papers
                (doi, title, authors_json, abstract, year, journal, citation_count, source, url, keywords_json, extra_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            return cursor.rowcount > 0

    def upsert_many(self, papers: list[Paper], deduplicate_by_doi: bool = True) -> int:
        """Insert or replace multiple papers. Returns count of stored papers."""
        seen: set[str] = set()
        count = 0
        for p in papers:
            key = (p.doi or p.title or "").strip().lower()
            if not key:
                continue
            if deduplicate_by_doi and key in seen:
                continue
            seen.add(key)
            self.upsert(p)
            count += 1
        return count

    def get_all(self, order_by: str = "citation_count DESC") -> list[Paper]:
        """Return all papers, optionally ordered. order_by must be in allowlist (SQL-safe)."""
        allowed = {"citation_count DESC", "year DESC", "title", "citation_count ASC", "year ASC"}
        if order_by not in allowed:
            order_by = "citation_count DESC"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM papers ORDER BY " + order_by)
            return [self._row_to_paper(tuple(r)) for r in cursor.fetchall()]

    def get_by_dois(self, dois: list[str]) -> list[Paper]:
        """Return papers matching given DOIs."""
        if not dois:
            return []
        placeholders = ",".join("?" * len(dois))
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"SELECT * FROM papers WHERE doi IN ({placeholders})",
                dois,
            )
            return [self._row_to_paper(tuple(r)) for r in cursor.fetchall()]

    def export_json(self, path: str | Path) -> None:
        """Export all papers to a single JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        papers = self.get_all()
        data = [p.model_dump() for p in papers]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
