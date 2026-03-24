"""PDF URL finder for papers-mcp — tries OA sources first, then Sci-Hub."""

import httpx

OPENALEX_BASE = "https://api.openalex.org"


async def find_pdf_url(doi: str, email: str = "", scihub_enabled: bool = False, scihub_mirror: str = "https://sci-hub.se") -> dict:
    """Find PDF URL for a paper. Tries OpenAlex OA, Unpaywall, then Sci-Hub."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 1. Try OpenAlex OA URL
        try:
            params = {}
            if email:
                params["mailto"] = email
            r = await client.get(f"{OPENALEX_BASE}/works/doi:{doi}", params=params)
            if r.status_code == 200:
                data = r.json()
                oa_url = data.get("open_access", {}).get("oa_url")
                if oa_url:
                    return {"url": oa_url, "source": "openalex_oa"}
        except httpx.HTTPError:
            pass

        # 2. Try Unpaywall
        try:
            params = {"email": email} if email else {}
            r = await client.get(f"https://api.unpaywall.org/v2/{doi}", params=params)
            if r.status_code == 200:
                data = r.json()
                best = data.get("best_oa_location") or {}
                if best.get("url_for_pdf"):
                    return {"url": best["url_for_pdf"], "source": "unpaywall"}
        except httpx.HTTPError:
            pass

        # 3. Fallback to Sci-Hub (opt-in only)
        if scihub_enabled:
            return {"url": f"{scihub_mirror}/{doi}", "source": "scihub"}

        return {"url": None, "source": None, "message": "No open-access PDF found. Enable Sci-Hub fallback with SCIHUB_ENABLED=true."}
