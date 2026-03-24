# papers-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![MCP stdio](https://img.shields.io/badge/MCP-stdio-orange)](https://modelcontextprotocol.io)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A local MCP server that turns Claude into your personal research assistant — it searches papers, finds PDFs, tracks citations, and keeps you up to date. No API keys needed.

## The killer feature: your morning paper briefing

Schedule a daily or weekly action and Claude will greet you with something like:

> **Good morning! Here are some new papers you might find interesting:**
>
> 1. *[paper title]* — Journal Name, 2026-03-18, 12 citations, [PDF](...)
> 2. *[paper title]* — Journal Name, 2026-03-15, 8 citations
> 3. *[paper title]* — Journal Name, 2026-03-20, 3 citations, [PDF](...)
>
> I've auto-saved the ones with 10+ citations. Want me to find the PDF for any of them?

To set this up, create a **scheduled action** in Claude Desktop (Cowork > Scheduled Actions):

```text
Use the papers-mcp tools to:
1. Get my research context
2. Check for new papers in the last 7 days
3. Present the top 5 as a numbered list (title, authors, journal, date, citations)
4. Include PDF links for open access papers
5. Save papers with more than 10 citations with tag "weekly-digest"
```

You can create as many scheduled actions as you want — citation alerts every Friday, a monthly literature review, tracking specific authors, trend detection, etc.

## Why not just ask Claude directly?

Claude already knows a lot about science, but it has limits:

| | Claude alone | Claude + papers-mcp |
| --- | --- | --- |
| **Data** | Training data (may be outdated) | Live OpenAlex API (250M+ works, updated daily) |
| **Your profile** | You explain your field every time | Knows your keywords, coauthors, and journals automatically |
| **PDFs** | Can't fetch them | Finds open-access PDFs via OpenAlex and Unpaywall |
| **Citations** | Can't track them | Monitors who cites your papers |
| **Memory** | Forgets between sessions | SQLite library persists your saved papers and profile |
| **Automation** | Manual every time | Schedule daily/weekly digests that run unattended |
| **BibTeX** | Generates approximate entries | Exports real metadata from your saved library |
| **Hallucination risk** | May invent papers | Every result comes from OpenAlex with real DOIs |

## Installation

```bash
git clone [https://github.com/pacs27/papers-mcp.git](https://github.com/pacs27/papers-mcp.git)
cd papers-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r servers/requirements.txt
```

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```jsonc
{
  "mcpServers": {
    "papers-mcp": {
      "command": "/absolute/path/to/papers-mcp/.venv/bin/python3",
      "args": ["/absolute/path/to/papers-mcp/servers/scholar_server.py"],
      "env": {
        "SCHOLAR_DB_PATH": "/absolute/path/to/papers-mcp/data/scholar.db",
        "OPENALEX_EMAIL": "your-email@example.com",
        "SCIHUB_ENABLED": "false"
      }
    }
  }
}
```

Restart Claude Desktop. Done.

## Quick start

**1. Build your profile** (one-time):

```text
Import my papers from ORCID 0000-0000-0000-0000
```

This imports all your publications and extracts keywords, coauthors, and journals automatically.

**2. Try it out:**

```text
What's new this week in my research area?
Find the top cited papers on crop modeling
Get the PDF for that last paper
Who cited my papers this month?
Export my saved papers as BibTeX
```

## All 14 tools

| Tool | What it does |
| --- | --- |
| `search_papers` | Search OpenAlex (sort by relevance, citations, or date; filter by min citations and date range) |
| `get_paper_details` | Full metadata for a single paper |
| `get_pdf_url` | Find PDF via OpenAlex OA and Unpaywall (Sci-Hub opt-in via `SCIHUB_ENABLED=true`) |
| `get_citations` | Papers that cite a given work |
| `find_related_papers` | Similar papers via OpenAlex's similarity graph |
| `add_my_paper` | Register your own paper by DOI |
| `import_from_orcid` | Bulk-import all your papers from ORCID |
| `get_research_context` | Your research profile in ~100 words |
| `check_new_papers` | New papers matching your profile keywords |
| `track_my_citations` | New citations on your papers |
| `get_author_papers` | Recent papers by a specific researcher |
| `save_paper` | Save to local library with tags and notes |
| `list_saved_papers` | Browse your library, filter by tag |
| `export_bibtex` | Export saved papers as BibTeX for LaTeX/Overleaf |

## More scheduled action ideas

**Citation monitoring** (every Friday):

```text
Check who cited my papers in the last 30 days.
Show which of my papers got cited and by whom.
Save citing papers with tag "cites-my-work".
```

**Author tracking** (every Wednesday):

```text
Check what my main coauthors published in the last 14 days.
Search for new papers on my top keywords from the last 14 days.
Highlight any that cite my work.
```

**Monthly literature review** (1st of each month):

```text
Search the most cited papers on my top 3 keywords from the last 90 days.
Write a 500-word summary organized by topic.
Export as BibTeX.
```

## License

MIT
