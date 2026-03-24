"""OpenAlex API client for papers-mcp."""

import httpx

OPENALEX_BASE = "https://api.openalex.org"


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """OpenAlex stores abstracts as inverted index. Reconstruct to plain text."""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


def _parse_paper(w: dict, truncate_abstract: int = 0) -> dict:
    """Parse an OpenAlex work into a compact dict."""
    abstract = reconstruct_abstract(w.get("abstract_inverted_index"))

    authors = ", ".join(
        a["author"]["display_name"]
        for a in w.get("authorships", [])[:3]
    )
    source = (w.get("primary_location") or {}).get("source") or {}
    oa = w.get("open_access", {})

    # Extract concept names
    concepts = [
        c.get("display_name", "")
        for c in w.get("concepts", [])
        if c.get("score", 0) > 0.3
    ]

    paper = {
        "id": w.get("id", ""),
        "title": w.get("title", ""),
        "date": w.get("publication_date", ""),
        "authors": authors,
        "source": source.get("display_name", "N/A"),
        "doi": w.get("doi", ""),
        "cited_by": w.get("cited_by_count", 0),
        "is_oa": oa.get("is_oa", False),
        "abstract": (abstract[:truncate_abstract] if truncate_abstract else abstract),
        "concepts": concepts,
    }
    return paper


async def search_openalex(
    query: str,
    from_date: str = "",
    to_date: str = "",
    sort: str = "relevance",
    per_page: int = 10,
    email: str = "",
    min_citations: int = 0,
) -> dict:
    """Search papers in OpenAlex."""
    filters = []
    if from_date:
        filters.append(f"from_publication_date:{from_date}")
    if to_date:
        filters.append(f"to_publication_date:{to_date}")
    if min_citations > 0:
        filters.append(f"cited_by_count:>{min_citations}")

    sort_map = {
        "date": "publication_date:desc",
        "citations": "cited_by_count:desc",
        "relevance": "relevance_score:desc",
    }

    params = {
        "search": query,
        "sort": sort_map.get(sort, "publication_date:desc"),
        "per_page": per_page,
    }
    if email:
        params["mailto"] = email
    if filters:
        params["filter"] = ",".join(filters)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{OPENALEX_BASE}/works", params=params)
        r.raise_for_status()
        data = r.json()

    papers = [_parse_paper(w, truncate_abstract=200) for w in data.get("results", [])]
    return {"total": data.get("meta", {}).get("count", 0), "papers": papers}


async def get_works_by_orcid(orcid: str, email: str = "", per_page: int = 50) -> dict:
    """Get all works by an author via their ORCID.
    First resolves ORCID to an OpenAlex author ID, then fetches works."""
    orcid_clean = orcid.replace("https://orcid.org/", "").strip()
    params = {"per_page": 1}
    if email:
        params["mailto"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        # Resolve ORCID to OpenAlex author ID
        r = await client.get(
            f"{OPENALEX_BASE}/authors/orcid:{orcid_clean}", params=params
        )
        if r.status_code != 200:
            return {"total": 0, "papers": [], "error": f"ORCID {orcid_clean} not found in OpenAlex"}

        author = r.json()
        author_id = author.get("id", "")
        author_name = author.get("display_name", "")

        # Fetch works by author ID
        work_params = {
            "filter": f"author.id:{author_id}",
            "sort": "publication_date:desc",
            "per_page": per_page,
        }
        if email:
            work_params["mailto"] = email

        r2 = await client.get(f"{OPENALEX_BASE}/works", params=work_params)
        r2.raise_for_status()
        data = r2.json()

    papers = [_parse_paper(w) for w in data.get("results", [])]
    return {
        "total": data.get("meta", {}).get("count", 0),
        "author_name": author_name,
        "author_id": author_id,
        "papers": papers,
    }


async def get_related_works(paper_id: str, email: str = "") -> dict:
    """Get related works for a paper using OpenAlex's related_works field."""
    # First get the paper to extract related_works IDs
    if paper_id.startswith("10.") or paper_id.startswith("https://doi.org/"):
        doi = paper_id.replace("https://doi.org/", "")
        url = f"{OPENALEX_BASE}/works/doi:{doi}"
    else:
        url = f"{OPENALEX_BASE}/works/{paper_id}" if not paper_id.startswith("http") else paper_id

    params = {}
    if email:
        params["mailto"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        work = r.json()

        related_ids = work.get("related_works", [])[:10]
        if not related_ids:
            return {"total": 0, "papers": [], "source_title": work.get("title", "")}

        # Fetch related works using OR filter
        openalex_filter = "|".join(related_ids)
        r2 = await client.get(
            f"{OPENALEX_BASE}/works",
            params={"filter": f"openalex:{openalex_filter}", "per_page": 10,
                    **({"mailto": email} if email else {})},
        )
        r2.raise_for_status()
        data = r2.json()

    papers = [_parse_paper(w, truncate_abstract=200) for w in data.get("results", [])]
    return {"total": len(papers), "papers": papers, "source_title": work.get("title", "")}


async def get_author_works(
    author_name: str = "", author_id: str = "", email: str = "",
    from_date: str = "", per_page: int = 10,
) -> dict:
    """Get recent papers by a specific author (by name search or OpenAlex author ID)."""
    mailto = {"mailto": email} if email else {}

    async with httpx.AsyncClient(timeout=30) as client:
        resolved_id = author_id
        resolved_name = author_name

        if not resolved_id and author_name:
            # Resolve author name to OpenAlex author ID
            r = await client.get(
                f"{OPENALEX_BASE}/authors",
                params={"search": author_name, "per_page": 1, **mailto},
            )
            r.raise_for_status()
            authors = r.json().get("results", [])
            if not authors:
                return {"total": 0, "papers": [], "error": f"Author '{author_name}' not found"}
            resolved_id = authors[0]["id"]
            resolved_name = authors[0].get("display_name", author_name)

        if not resolved_id:
            return {"total": 0, "papers": [], "error": "Provide author_name or author_id"}

        # Fetch works
        filters = [f"author.id:{resolved_id}"]
        if from_date:
            filters.append(f"from_publication_date:{from_date}")

        r = await client.get(
            f"{OPENALEX_BASE}/works",
            params={
                "filter": ",".join(filters),
                "sort": "publication_date:desc",
                "per_page": per_page,
                **mailto,
            },
        )
        r.raise_for_status()
        data = r.json()

    papers = [_parse_paper(w, truncate_abstract=200) for w in data.get("results", [])]
    return {
        "total": data.get("meta", {}).get("count", 0),
        "author_name": resolved_name,
        "author_id": resolved_id,
        "papers": papers,
    }


async def get_work_details(paper_id: str, email: str = "") -> dict:
    """Get full details of a single paper by OpenAlex ID or DOI."""
    # Handle DOI format
    if paper_id.startswith("10."):
        url = f"{OPENALEX_BASE}/works/doi:{paper_id}"
    elif paper_id.startswith("https://doi.org/"):
        doi = paper_id.replace("https://doi.org/", "")
        url = f"{OPENALEX_BASE}/works/doi:{doi}"
    else:
        url = f"{OPENALEX_BASE}/works/{paper_id}" if not paper_id.startswith("http") else paper_id

    params = {}
    if email:
        params["mailto"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        w = r.json()

    paper = _parse_paper(w)
    # Add extra fields for detailed view
    oa = w.get("open_access", {})
    paper["oa_url"] = oa.get("oa_url", "")
    paper["referenced_works"] = len(w.get("referenced_works", []))
    return paper


async def get_citing_works(
    paper_id: str, sort: str = "date", email: str = "", per_page: int = 10
) -> dict:
    """Get papers that cite a given paper."""
    # Extract the OpenAlex ID path
    if paper_id.startswith("https://openalex.org/"):
        oa_id = paper_id
    else:
        oa_id = paper_id

    sort_map = {
        "date": "publication_date:desc",
        "citations": "cited_by_count:desc",
    }

    params = {
        "filter": f"cites:{oa_id}",
        "sort": sort_map.get(sort, "publication_date:desc"),
        "per_page": per_page,
    }
    if email:
        params["mailto"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{OPENALEX_BASE}/works", params=params)
        r.raise_for_status()
        data = r.json()

    papers = [_parse_paper(w, truncate_abstract=200) for w in data.get("results", [])]
    return {"total": data.get("meta", {}).get("count", 0), "papers": papers}
