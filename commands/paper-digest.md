---
description: Run daily paper digest
allowed-tools: ["mcp__papers-mcp__get_research_context",
                "mcp__papers-mcp__check_new_papers",
                "mcp__papers-mcp__save_paper"]
---

Execute a research digest:

1. Call get_research_context to load the user's research profile
2. Call check_new_papers with since_days=7
3. Present results as a compact numbered list:
   For each paper: number, title, authors (max 2), journal, date, citations
4. At the end, ask: "¿Quieres guardar alguno? Dime los números."
5. If the user gives numbers, call save_paper for each one

Keep the output concise. No lengthy explanations.
