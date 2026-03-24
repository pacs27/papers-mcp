---
name: research-assistant
description: >
  This skill should be used when the user asks to "search papers",
  "find publications", "check new papers", "paper digest",
  "buscar papers", "buscar publicaciones", "papers nuevos",
  "import from ORCID", "who cited my papers", "related papers",
  "export bibtex", "follow author", or needs help with academic
  research, literature review, or citation tracking.
version: 0.2.0
---

# Research Assistant

Assist the user with academic paper search, tracking, and analysis
using the papers-mcp MCP tools (14 tools available).

## Principles — context efficiency

1. NEVER request full abstracts of more than 3 papers at once
2. ALWAYS use `get_research_context` FIRST to understand the user's
   research profile before searching
3. Use `search_papers` with specific queries derived from the profile
4. Only call `get_paper_details` when the user asks about a specific paper
5. When presenting results, show a compact table:
   Title | Authors | Date | Citas | OA
6. For "top papers" or "best papers" queries, use sort="citations"
   and optionally min_citations to filter noise
7. For "recent" or "new" queries, use sort="date" or from_date filter
8. Default sort is "relevance" — best for general topic searches

## Workflow for first-time setup (ORCID)

1. User provides ORCID
2. Call `import_from_orcid` → bulk-import all papers
3. Call `get_research_context` → show the generated profile
4. Confirm: "Your profile is ready with X papers. Keywords: ..."

## Workflow for daily digest

1. Call `get_research_context` → get keywords and profile
2. Call `check_new_papers` → get papers from last 7 days
3. Present results grouped by relevance to user's research
4. Ask which papers to save with `save_paper`

## Workflow for searching

1. Call `get_research_context` → understand profile
2. Call `search_papers` with user's query
3. Present compact results (max 10)
4. If user wants PDF → call `get_pdf_url`
5. If user wants to save → call `save_paper`

## Workflow for citation monitoring

1. Call `track_my_citations` with appropriate since_days
2. Present which papers got cited and by whom
3. Offer to save notable citing papers

## Workflow for related papers

1. User gives a paper (DOI or OpenAlex ID)
2. Call `find_related_papers`
3. Present compact results
4. Offer to save or get details on interesting ones

## Workflow for following a researcher

1. User gives author name or ID
2. Call `get_author_papers` with optional from_date
3. Present recent publications
4. Offer to save interesting ones

## Workflow for BibTeX export

1. Call `export_bibtex` with optional tag filter
2. Present the BibTeX output
3. User can copy-paste into their .bib file

## Anti-hallucination rules

- NEVER invent DOIs, titles, or author names
- ALWAYS use tool results as ground truth
- If a search returns 0 results, say so — don't guess
- When citing a paper, always include the DOI
- If unsure about a paper's content, use `get_paper_details`
