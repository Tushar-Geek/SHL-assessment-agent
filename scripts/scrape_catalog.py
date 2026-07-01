from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import HttpUrl, TypeAdapter

CATALOG_URL = "https://www.shl.com/solutions/products/product-catalog/"
LOGGER = logging.getLogger(__name__)
URL_ADAPTER = TypeAdapter(HttpUrl)


@dataclass
class ScrapedAssessment:
    name: str
    description: str = ""
    skills_measured: list[str] = field(default_factory=list)
    duration: int | None = None
    remote_testing: bool | None = None
    languages: list[str] = field(default_factory=list)
    test_type: str = ""
    job_level: list[str] = field(default_factory=list)
    assessment_family: str = ""
    catalog_url: str = ""
    structured_metadata: dict[str, object] = field(default_factory=dict)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape SHL Individual Test Solutions catalog")
    parser.add_argument("--output", default="data/catalog.json")
    parser.add_argument("--start-url", default=CATALOG_URL)
    parser.add_argument("--browser", action="store_true", help="Use Playwright for JS-rendered pages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    html_pages = await collect_catalog_pages(args.start_url, use_browser=args.browser)
    records = await parse_records(html_pages, use_browser=args.browser)
    records = dedupe(records)
    await validate_urls(records)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([asdict(item) for item in records], indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Wrote %s SHL catalog records to %s", len(records), output)


async def collect_catalog_pages(start_url: str, use_browser: bool = False) -> list[tuple[str, str]]:
    if use_browser:
        return await collect_with_playwright(start_url)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        response = await client.get(start_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        pages = [(str(response.url), response.text)]
        for href in sorted({a.get("href") for a in soup.select("a[href]") if a.get("href")}):
            url = urljoin(str(response.url), href)
            if _same_host(start_url, url) and "product-catalog" in url and url != str(response.url):
                try:
                    page = await client.get(url)
                    if page.status_code == 200:
                        pages.append((str(page.url), page.text))
                except httpx.HTTPError as exc:
                    LOGGER.warning("Skipping %s: %s", url, exc)
        return pages


async def collect_with_playwright(start_url: str) -> list[tuple[str, str]]:
    from playwright.async_api import async_playwright

    pages: list[tuple[str, str]] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0")
        await page.goto(start_url, wait_until="networkidle", timeout=60000)
        pages.append((page.url, await page.content()))
        links = await page.locator("a[href]").evaluate_all("els => [...new Set(els.map(a => a.href))]")
        for url in links:
            if _same_host(start_url, url) and "product-catalog" in url:
                try:
                    await page.goto(url, wait_until="networkidle", timeout=60000)
                    pages.append((page.url, await page.content()))
                except Exception as exc:
                    LOGGER.warning("Skipping %s: %s", url, exc)
        await browser.close()
    return pages


async def parse_records(html_pages: list[tuple[str, str]], use_browser: bool = False) -> list[ScrapedAssessment]:
    records: list[ScrapedAssessment] = []
    detail_urls: set[str] = set()
    for page_url, html in html_pages:
        soup = BeautifulSoup(html, "html.parser")
        detail_urls.update(_extract_detail_urls(soup, page_url))
        records.extend(_parse_table_records(soup, page_url))
    if detail_urls:
        detail_pages = await _fetch_detail_pages(sorted(detail_urls), use_browser)
        records.extend(_parse_detail_page(url, html) for url, html in detail_pages)
    return [record for record in records if _looks_individual_test(record)]


def _extract_detail_urls(soup: BeautifulSoup, base_url: str) -> set[str]:
    urls = set()
    for link in soup.select("a[href]"):
        text = link.get_text(" ", strip=True).lower()
        href = link.get("href") or ""
        url = urljoin(base_url, href)
        if "product-catalog" in url and ("view" in url or text):
            urls.add(url)
    return urls


def _parse_table_records(soup: BeautifulSoup, page_url: str) -> list[ScrapedAssessment]:
    records: list[ScrapedAssessment] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(cells) < 2:
            continue
        link = row.select_one("a[href]")
        url = urljoin(page_url, link.get("href")) if link else page_url
        metadata = {f"column_{index}": value for index, value in enumerate(cells)}
        records.append(
            ScrapedAssessment(
                name=cells[0],
                test_type=_first_nonempty(cells[1:3]),
                remote_testing=_parse_bool(" ".join(cells)),
                duration=_parse_duration(" ".join(cells)),
                catalog_url=url,
                structured_metadata=metadata,
            )
        )
    return records


def _parse_detail_page(url: str, html: str) -> ScrapedAssessment:
    soup = BeautifulSoup(html, "html.parser")
    name = _first_text(soup, ["h1", "h2", "title"])
    text = soup.get_text("\n", strip=True)
    metadata = _definition_metadata(soup)
    description = _description_from_text(text, name)
    skills = _split_list(metadata.get("Skills", "") or metadata.get("Knowledge, Skills, Abilities", ""))
    languages = _split_list(metadata.get("Languages", ""))
    job_level = _split_list(metadata.get("Job levels", "") or metadata.get("Job Level", ""))
    test_type = metadata.get("Test Type", "") or metadata.get("Assessment Type", "")
    family = metadata.get("Assessment Family", "") or metadata.get("Family", "")
    return ScrapedAssessment(
        name=name,
        description=description,
        skills_measured=skills,
        duration=_parse_duration(text),
        remote_testing=_parse_bool(text),
        languages=languages,
        test_type=test_type,
        job_level=job_level,
        assessment_family=family,
        catalog_url=url,
        structured_metadata=metadata,
    )


def _definition_metadata(soup: BeautifulSoup) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for dt in soup.select("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            metadata[dt.get_text(" ", strip=True).rstrip(":")] = dd.get_text(" ", strip=True)
    text = soup.get_text("\n", strip=True)
    labels = ["Test Type", "Assessment Type", "Duration", "Remote Testing", "Languages", "Job Level", "Assessment Family", "Skills"]
    for label in labels:
        match = re.search(rf"{label}\s*:?\s*([^\n]+)", text, flags=re.I)
        if match:
            metadata.setdefault(label, match.group(1).strip())
    return metadata


async def _fetch_detail_pages(urls: list[str], use_browser: bool) -> list[tuple[str, str]]:
    if use_browser:
        return await _fetch_detail_pages_browser(urls)
    pages: list[tuple[str, str]] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for url in urls:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    pages.append((str(response.url), response.text))
            except httpx.HTTPError as exc:
                LOGGER.warning("Detail fetch failed for %s: %s", url, exc)
    return pages


async def _fetch_detail_pages_browser(urls: list[str]) -> list[tuple[str, str]]:
    from playwright.async_api import async_playwright

    pages = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0")
        for url in urls:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            pages.append((page.url, await page.content()))
        await browser.close()
    return pages


def dedupe(records: list[ScrapedAssessment]) -> list[ScrapedAssessment]:
    by_url: dict[str, ScrapedAssessment] = {}
    for record in records:
        if not record.name or not record.catalog_url:
            continue
        current = by_url.get(record.catalog_url)
        if current is None or len(record.description) > len(current.description):
            by_url[record.catalog_url] = record
    return sorted(by_url.values(), key=lambda item: item.name.lower())


async def validate_urls(records: list[ScrapedAssessment]) -> None:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for record in records:
            URL_ADAPTER.validate_python(record.catalog_url)
            response = await client.head(record.catalog_url)
            if response.status_code >= 400:
                response = await client.get(record.catalog_url)
            if response.status_code >= 400:
                raise ValueError(f"Invalid catalog URL {record.catalog_url}: {response.status_code}")


def _looks_individual_test(record: ScrapedAssessment) -> bool:
    haystack = " ".join([record.name, record.description, record.test_type, str(record.structured_metadata)]).lower()
    if "job solution" in haystack:
        return False
    return bool(record.catalog_url)


def _same_host(left: str, right: str) -> bool:
    return urlparse(left).netloc == urlparse(right).netloc


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        item = soup.select_one(selector)
        if item:
            return item.get_text(" ", strip=True)
    return ""


def _description_from_text(text: str, name: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if line != name and len(line) > 60:
            return line
    return ""


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;|/]", value or "") if part.strip()]


def _parse_bool(text: str) -> bool | None:
    lowered = text.lower()
    if re.search(r"remote testing\s*:?[\s\n]*(yes|available|true)", lowered) or "remote testing yes" in lowered:
        return True
    if re.search(r"remote testing\s*:?[\s\n]*(no|false)", lowered) or "remote testing no" in lowered:
        return False
    return None


def _parse_duration(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*(?:minutes|minute|mins|min)\b", text, flags=re.I)
    return int(match.group(1)) if match else None


def _first_nonempty(values: list[str]) -> str:
    return next((value for value in values if value), "")


if __name__ == "__main__":
    asyncio.run(main())
