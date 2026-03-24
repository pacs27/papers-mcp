#!/usr/bin/env python3
"""papers-mcp server."""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Add servers dir to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from db import Database
from openalex import (
    search_openalex, get_work_details, get_citing_works,
    get_works_by_orcid, get_related_works, get_author_works,
)
from pdf_fetcher import find_pdf_url

# Config
DB_PATH = os.environ.get("SCHOLAR_DB_PATH", str(Path(__file__).parent.parent / "data" / "scholar.db"))
EMAIL = os.environ.get("OPENALEX_EMAIL", "")
SCIHUB = os.environ.get("SCIHUB_MIRROR", "https://sci-hub.se")
SCIHUB_ENABLED = os.environ.get("SCIHUB_ENABLED", "false").lower() in ("true", "1", "yes")

db = Database(DB_PATH)
mcp = FastMCP("papers-mcp")


@mcp.tool()
async def search_papers(
    query: str,
    from_date: str = "",
    to_date: str = "",
    sort: str = "relevance",
    min_citations: int = 0,
) -> str:
    """Search academic papers via OpenAlex. Returns max 10 compact results.

    Sort options:
    - 'relevance' (default): best match for the query — use for general searches
    - 'citations': most cited first — use for finding seminal/top papers
    - 'date': most recent first — use only when user wants latest papers

    Use min_citations to filter out low-impact papers (e.g. min_citations=50
    for established papers, min_citations=200 for seminal works)."""
    results = await search_openalex(
        query, from_date, to_date, sort, per_page=10, email=EMAIL,
        min_citations=min_citations,
    )
    return json.dumps(results, ensure_ascii=False)


@mcp.tool()
async def get_paper_details(paper_id: str) -> str:
    """Get full details of a single paper by OpenAlex ID or DOI.
    Use this when you need the complete abstract, concepts, or OA URL."""
    details = await get_work_details(paper_id, email=EMAIL)
    return json.dumps(details, ensure_ascii=False)


@mcp.tool()
async def get_pdf_url(doi: str) -> str:
    """Find PDF URL for a paper. Tries open-access sources (OpenAlex, Unpaywall).
    Sci-Hub fallback is available only if SCIHUB_ENABLED=true is set.
    Pass just the DOI (e.g. '10.1234/example'), not a full URL."""
    # Clean DOI if full URL was passed
    if doi.startswith("https://doi.org/"):
        doi = doi.replace("https://doi.org/", "")
    result = await find_pdf_url(doi, email=EMAIL, scihub_enabled=SCIHUB_ENABLED, scihub_mirror=SCIHUB)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def get_citations(paper_id: str, sort: str = "date") -> str:
    """Get papers that cite a given paper. paper_id should be an OpenAlex ID.
    Sort options: 'date', 'citations'."""
    results = await get_citing_works(paper_id, sort, email=EMAIL)
    return json.dumps(results, ensure_ascii=False)


@mcp.tool()
async def save_paper(paper_id: str, tags: str = "", notes: str = "") -> str:
    """Save a paper to local library. Tags as comma-separated string.
    paper_id can be an OpenAlex ID or DOI."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    details = await get_work_details(paper_id, email=EMAIL)
    db.save_paper(details, tag_list, notes)
    return json.dumps({"saved": True, "title": details["title"]}, ensure_ascii=False)


@mcp.tool()
async def list_saved_papers(tag: str = "", limit: int = 10) -> str:
    """List papers in local library, optionally filtered by tag."""
    papers = db.list_saved(tag=tag, limit=limit)
    return json.dumps(papers, ensure_ascii=False)


@mcp.tool()
async def add_my_paper(doi: str) -> str:
    """Register one of the user's own papers to build research profile.
    This helps the system understand your research interests."""
    if doi.startswith("https://doi.org/"):
        doi = doi.replace("https://doi.org/", "")
    details = await get_work_details(f"doi:{doi}", email=EMAIL)
    db.add_my_paper(details)
    return json.dumps({"added": True, "title": details["title"]}, ensure_ascii=False)


@mcp.tool()
async def get_research_context() -> str:
    """Get a compact summary of the user's research profile.
    ALWAYS call this before searching to understand context.
    Returns a short text paragraph, not a large JSON."""
    profile = db.get_research_profile()

    if profile["num_my_papers"] == 0 and profile["num_saved"] == 0:
        return ("No hay perfil de investigación todavía. "
                "Usa add_my_paper con tu DOI para registrar tus papers, "
                "o save_paper para guardar papers de interés.")

    parts = []
    parts.append(f"Perfil: {profile['num_my_papers']} papers propios")
    if profile["keywords"]:
        parts.append(f"Temas: {', '.join(profile['keywords'][:10])}")
    if profile["coauthors"]:
        parts.append(f"Coautores: {', '.join(profile['coauthors'][:5])}")
    if profile["sources"]:
        parts.append(f"Revistas: {', '.join(profile['sources'][:5])}")
    parts.append(f"Papers guardados: {profile['num_saved']}")
    if profile.get("recent_saved_topics"):
        parts.append(f"Últimos intereses: {', '.join(profile['recent_saved_topics'])}")

    return ". ".join(parts) + "."


@mcp.tool()
async def check_new_papers(since_days: int = 7) -> str:
    """Check for new papers since last check, based on research profile keywords.
    Combines profile keywords into search queries and deduplicates results."""
    profile = db.get_research_profile()
    keywords = profile["keywords"]

    if not keywords:
        return json.dumps({
            "error": "No hay perfil de investigación. Usa add_my_paper primero."
        })

    from_date = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
    queries = _generate_queries(keywords)

    all_papers = {}
    for q in queries[:3]:
        results = await search_openalex(q, from_date=from_date, per_page=10, email=EMAIL)
        for p in results.get("papers", []):
            doi = p.get("doi", "")
            if doi and doi not in all_papers:
                all_papers[doi] = p

    db.log_check(queries[:3], len(all_papers))

    papers_list = sorted(all_papers.values(), key=lambda x: x.get("date", ""), reverse=True)[:10]

    return json.dumps({
        "queries_used": queries[:3],
        "new_papers": papers_list,
        "total_found": len(all_papers),
    }, ensure_ascii=False)


@mcp.tool()
async def import_from_orcid(orcid: str) -> str:
    """Import all papers from an ORCID profile and register them as your own papers.
    This bulk-builds your research profile in one step.
    ORCID format: '0000-0002-1234-5678' (with or without https://orcid.org/ prefix).

    Ideal for first-time setup. After importing, use get_research_context to see
    your generated profile."""
    # Clean ORCID
    orcid = orcid.replace("https://orcid.org/", "").strip()

    results = await get_works_by_orcid(orcid, email=EMAIL)
    imported = []
    for p in results.get("papers", []):
        if p.get("doi"):
            db.add_my_paper(p)
            imported.append(p["title"])

    return json.dumps({
        "orcid": orcid,
        "total_found": results["total"],
        "imported": len(imported),
        "titles": imported[:10],
        "message": f"Imported {len(imported)} papers. Use get_research_context to see your profile."
    }, ensure_ascii=False)


@mcp.tool()
async def track_my_citations(since_days: int = 30) -> str:
    """Check for NEW citations on your own papers since a given period.
    Perfect for scheduled weekly/monthly monitoring.

    Returns a summary: which of your papers got cited and by whom.
    Only shows citations published after the cutoff date."""
    my_papers = db.get_all_my_papers()
    if not my_papers:
        return json.dumps({"error": "No own papers registered. Use add_my_paper or import_from_orcid first."})

    from_date = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
    citation_report = []

    for paper in my_papers:
        oa_id = paper.get("openalex_id", "")
        if not oa_id:
            continue

        results = await get_citing_works(oa_id, sort="date", email=EMAIL, per_page=5)
        # Filter only recent citations
        new_cites = [
            p for p in results.get("papers", [])
            if p.get("date", "") >= from_date
        ]
        if new_cites:
            citation_report.append({
                "your_paper": paper["title"],
                "your_doi": paper["doi"],
                "new_citations": len(new_cites),
                "total_citations": results["total"],
                "recent_citers": [
                    {"title": c["title"], "authors": c["authors"], "date": c["date"]}
                    for c in new_cites[:3]
                ],
            })

    return json.dumps({
        "period": f"last {since_days} days",
        "papers_checked": len(my_papers),
        "papers_with_new_citations": len(citation_report),
        "report": citation_report,
    }, ensure_ascii=False)


@mcp.tool()
async def find_related_papers(paper_id: str) -> str:
    """Find papers related to a given paper using OpenAlex's similarity graph.
    paper_id can be an OpenAlex ID or DOI.
    Useful for expanding a literature review from a seed paper."""
    results = await get_related_works(paper_id, email=EMAIL)
    return json.dumps(results, ensure_ascii=False)


@mcp.tool()
async def get_author_papers(author_name: str = "", author_id: str = "", from_date: str = "") -> str:
    """Get recent papers by a specific researcher.
    Search by name (e.g. 'García-Vila') or OpenAlex author ID.
    Use from_date (YYYY-MM-DD) to only see recent publications.

    Great for tracking what collaborators or key researchers in your field
    are publishing."""
    results = await get_author_works(
        author_name=author_name, author_id=author_id,
        email=EMAIL, from_date=from_date,
    )
    return json.dumps(results, ensure_ascii=False)


@mcp.tool()
async def export_bibtex(tag: str = "") -> str:
    """Export saved papers as BibTeX entries for use in LaTeX/Overleaf.
    Optionally filter by tag. Returns a ready-to-use .bib string."""
    bib = db.export_bibtex(tag=tag)
    if not bib:
        return "No saved papers to export. Use save_paper first."
    return bib


def _generate_queries(keywords: list) -> list:
    """Generate search queries by combining profile keywords."""
    if len(keywords) < 2:
        return keywords
    queries = []
    for i in range(0, min(len(keywords), 6), 2):
        if i + 1 < len(keywords):
            queries.append(f"{keywords[i]} {keywords[i + 1]}")
    return queries or keywords[:3]


if __name__ == "__main__":
    mcp.run(transport="stdio")
