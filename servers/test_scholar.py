#!/usr/bin/env python3
"""Tests for papers-mcp — searches AquaCrop-IoT and fetches PDF URLs."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from openalex import search_openalex, get_work_details, get_citing_works
from pdf_fetcher import find_pdf_url
from db import Database

EMAIL = os.environ.get("OPENALEX_EMAIL", "")
TEST_DB = str(Path(__file__).parent.parent / "data" / "test_scholar.db")

passed = 0
failed = 0


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name} — {detail}")


async def test_search_aquacrop_iot():
    """Search for AquaCrop IoT papers and verify results."""
    print("\n--- Test: search AquaCrop IoT ---")
    results = await search_openalex("AquaCrop IoT", per_page=5, email=EMAIL)

    report("returns total count", results["total"] > 0, f"total={results.get('total')}")
    report("returns papers list", len(results["papers"]) > 0, "empty papers list")

    if results["papers"]:
        p = results["papers"][0]
        report("paper has title", bool(p.get("title")), "missing title")
        report("paper has authors", bool(p.get("authors")), "missing authors")
        report("paper has date", bool(p.get("date")), "missing date")
        report("paper has doi", bool(p.get("doi")), "missing doi")
        report("abstract truncated <=200", len(p.get("abstract", "")) <= 200,
               f"len={len(p.get('abstract', ''))}")
        report("has concepts", isinstance(p.get("concepts"), list), "missing concepts")
        print(f"\n  First result: {p['title'][:80]}")
        print(f"  Authors: {p['authors']}")
        print(f"  DOI: {p['doi']}")
        print(f"  Date: {p['date']}, Citas: {p['cited_by']}, OA: {p['is_oa']}")
        return p
    return None


async def test_search_with_sort():
    """Search sorted by citations."""
    print("\n--- Test: search by citations ---")
    results = await search_openalex("AquaCrop IoT irrigation", sort="citations", per_page=3, email=EMAIL)

    report("returns results", len(results["papers"]) > 0)

    if len(results["papers"]) >= 2:
        cites = [p["cited_by"] for p in results["papers"]]
        report("sorted by citations desc", cites[0] >= cites[1],
               f"cites={cites}")
        print(f"  Top cited: {results['papers'][0]['title'][:70]} ({cites[0]} citas)")


async def test_get_paper_details(doi: str):
    """Get full details of a paper by DOI."""
    print(f"\n--- Test: get_paper_details (DOI: {doi}) ---")
    details = await get_work_details(f"doi:{doi}", email=EMAIL)

    report("has title", bool(details.get("title")))
    report("has full abstract", len(details.get("abstract", "")) > 0, "no abstract")
    report("has concepts", len(details.get("concepts", [])) > 0)
    report("has oa_url field", "oa_url" in details)
    report("has referenced_works count", "referenced_works" in details)

    print(f"  Title: {details['title'][:80]}")
    print(f"  Abstract length: {len(details.get('abstract', ''))} chars")
    print(f"  Concepts: {', '.join(details.get('concepts', [])[:5])}")
    print(f"  OA URL: {details.get('oa_url') or 'N/A'}")
    print(f"  References: {details.get('referenced_works')}")
    return details


async def test_get_pdf_url(doi: str):
    """Find PDF URL for a paper."""
    print(f"\n--- Test: get_pdf_url (DOI: {doi}) ---")
    # Clean DOI
    clean_doi = doi.replace("https://doi.org/", "")
    result = await find_pdf_url(clean_doi, email=EMAIL)

    report("has url", bool(result.get("url")), "no url returned")
    report("has source", result.get("source") in ("openalex_oa", "unpaywall", "scihub"),
           f"source={result.get('source')}")

    print(f"  PDF URL: {result['url']}")
    print(f"  Source: {result['source']}")
    return result


async def test_get_citations(openalex_id: str):
    """Get citations for a paper."""
    print(f"\n--- Test: get_citations ---")
    results = await get_citing_works(openalex_id, sort="date", email=EMAIL)

    report("returns total", "total" in results)
    report("returns papers list", isinstance(results.get("papers"), list))

    print(f"  Total citing papers: {results['total']}")
    if results["papers"]:
        p = results["papers"][0]
        print(f"  Most recent: {p['title'][:70]} ({p['date']})")


async def test_database():
    """Test database operations."""
    print("\n--- Test: database ---")
    import os
    # Clean up test db
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    db = Database(TEST_DB)

    # Test add_my_paper
    fake_paper = {
        "doi": "10.1234/test",
        "id": "https://openalex.org/W0000",
        "title": "Test Paper on AquaCrop",
        "authors": "Author A, Author B",
        "source": "Test Journal",
        "date": "2025-01-01",
        "concepts": ["AquaCrop", "IoT", "irrigation"],
        "abstract": "Test abstract",
        "cited_by": 10,
    }

    db.add_my_paper(fake_paper)
    my_papers = db.get_all_my_papers()
    report("add_my_paper works", len(my_papers) == 1)
    report("paper stored correctly", my_papers[0]["title"] == "Test Paper on AquaCrop")

    # Test save_paper
    db.save_paper(fake_paper, ["test", "aquacrop"], "My test notes")
    saved = db.list_saved()
    report("save_paper works", len(saved) == 1)
    report("tags stored", '"test"' in saved[0]["tags"])

    # Test filter by tag
    filtered = db.list_saved(tag="aquacrop")
    report("filter by tag works", len(filtered) == 1)
    empty = db.list_saved(tag="nonexistent")
    report("filter excludes non-matching", len(empty) == 0)

    # Test research profile
    profile = db.get_research_profile()
    report("profile has keywords", len(profile["keywords"]) > 0)
    report("profile has my_papers count", profile["num_my_papers"] == 1)
    report("profile has saved count", profile["num_saved"] == 1)
    print(f"  Keywords: {profile['keywords']}")
    print(f"  Coauthors: {profile['coauthors']}")

    # Test log_check
    db.log_check(["aquacrop iot"], 5)
    last = db.get_last_check()
    report("log_check works", last is not None)

    # Cleanup
    os.remove(TEST_DB)


async def main():
    global passed, failed

    print("=" * 60)
    print("papers-mcp — Integration Tests")
    print("=" * 60)

    # 1. Database tests (no network)
    await test_database()

    # 2. Search tests
    paper = await test_search_aquacrop_iot()
    await test_search_with_sort()

    if paper and paper.get("doi"):
        # 3. Paper details
        details = await test_get_paper_details(paper["doi"])

        # 4. PDF URL
        await test_get_pdf_url(paper["doi"])

        # 5. Citations
        if paper.get("id"):
            await test_get_citations(paper["id"])

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
