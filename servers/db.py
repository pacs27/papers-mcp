"""Database layer for papers-mcp — SQLite storage."""

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime


class Database:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS my_papers (
                doi TEXT PRIMARY KEY,
                openalex_id TEXT,
                title TEXT,
                authors TEXT,
                source TEXT,
                publication_date TEXT,
                concepts TEXT,
                abstract TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS saved_papers (
                doi TEXT PRIMARY KEY,
                openalex_id TEXT,
                title TEXT,
                authors TEXT,
                source TEXT,
                publication_date TEXT,
                cited_by INTEGER,
                abstract TEXT,
                tags TEXT,
                notes TEXT,
                saved_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS research_profile (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS check_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TEXT,
                queries_used TEXT,
                papers_found INTEGER
            );
        """)
        self.conn.commit()

    def add_my_paper(self, details: dict):
        concepts = json.dumps(details.get("concepts", []), ensure_ascii=False)
        self.conn.execute(
            """INSERT OR REPLACE INTO my_papers
               (doi, openalex_id, title, authors, source, publication_date, concepts, abstract)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                details.get("doi", ""),
                details.get("id", ""),
                details.get("title", ""),
                details.get("authors", ""),
                details.get("source", ""),
                details.get("date", ""),
                concepts,
                details.get("abstract", ""),
            ),
        )
        self.conn.commit()

    def save_paper(self, details: dict, tags: list, notes: str):
        tags_json = json.dumps(tags, ensure_ascii=False)
        self.conn.execute(
            """INSERT OR REPLACE INTO saved_papers
               (doi, openalex_id, title, authors, source, publication_date,
                cited_by, abstract, tags, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                details.get("doi", ""),
                details.get("id", ""),
                details.get("title", ""),
                details.get("authors", ""),
                details.get("source", ""),
                details.get("date", ""),
                details.get("cited_by", 0),
                details.get("abstract", ""),
                tags_json,
                notes,
            ),
        )
        self.conn.commit()

    def list_saved(self, tag: str = "", limit: int = 10) -> list:
        if tag:
            rows = self.conn.execute(
                """SELECT * FROM saved_papers
                   WHERE tags LIKE ?
                   ORDER BY saved_at DESC LIMIT ?""",
                (f'%"{tag}"%', limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM saved_papers ORDER BY saved_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_my_papers(self) -> list:
        rows = self.conn.execute("SELECT * FROM my_papers ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_all_saved_papers(self) -> list:
        rows = self.conn.execute("SELECT * FROM saved_papers ORDER BY saved_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_research_profile(self) -> dict:
        my_papers = self.get_all_my_papers()
        saved_papers = self.get_all_saved_papers()

        all_concepts = []
        for p in my_papers + saved_papers:
            concepts = json.loads(p.get("concepts") or "[]")
            all_concepts.extend(concepts)

        keyword_freq = Counter(all_concepts).most_common(15)

        all_authors = []
        for p in my_papers:
            if p.get("authors"):
                all_authors.extend(p["authors"].split(", "))
        coauthor_freq = Counter(all_authors).most_common(5)

        sources = list({p["source"] for p in my_papers if p.get("source")})

        recent_saved_topics = self._extract_recent_topics(saved_papers[:5])

        return {
            "num_my_papers": len(my_papers),
            "num_saved": len(saved_papers),
            "keywords": [k for k, _ in keyword_freq],
            "coauthors": [a for a, _ in coauthor_freq],
            "sources": sources,
            "recent_saved_topics": recent_saved_topics,
        }

    def _extract_recent_topics(self, papers: list) -> list:
        topics = []
        for p in papers:
            concepts = json.loads(p.get("concepts") or "[]")
            topics.extend(concepts[:2])
        return list(dict.fromkeys(topics))[:5]

    def log_check(self, queries: list, papers_found: int):
        self.conn.execute(
            "INSERT INTO check_log (checked_at, queries_used, papers_found) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), json.dumps(queries), papers_found),
        )
        self.conn.commit()

    def get_last_check(self) -> str | None:
        row = self.conn.execute(
            "SELECT checked_at FROM check_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["checked_at"] if row else None

    def export_bibtex(self, tag: str = "") -> str:
        papers = self.list_saved(tag=tag, limit=9999)
        entries = []
        for p in papers:
            doi = (p.get("doi") or "").replace("https://doi.org/", "")
            # Generate cite key: first author surname + year
            authors = p.get("authors", "")
            first_author = authors.split(",")[0].strip().split()[-1] if authors else "unknown"
            year = (p.get("publication_date") or "0000")[:4]
            cite_key = f"{first_author.lower()}{year}"

            entry = f"@article{{{cite_key},\n"
            entry += f"  title = {{{p.get('title', '')}}},\n"
            entry += f"  author = {{{p.get('authors', '')}}},\n"
            entry += f"  journal = {{{p.get('source', '')}}},\n"
            entry += f"  year = {{{year}}},\n"
            if doi:
                entry += f"  doi = {{{doi}}},\n"
            entry += "}"
            entries.append(entry)
        return "\n\n".join(entries)
