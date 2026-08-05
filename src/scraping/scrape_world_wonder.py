import re

import requests
from bs4 import BeautifulSoup, Comment

from src.config import Section, Version
from src.schema import UnifiedEntry


def get_era_from_comment(chart) -> str:
    """Extract the feature category from the LOC comment preceding the h2."""

    # Matches e.g. "LOC_NAMED_DESERT_ACCONA_DESERT_NAME" -> "Desert"
    LOC_COMMENT_RE = re.compile(r"LOC_ERA_([A-Z]+)_", re.IGNORECASE)

    for node in chart.children:
        if isinstance(node, Comment):
            m = LOC_COMMENT_RE.search(node)
            if m:
                return m.group(1).title()  # e.g. "AMERICA" -> "America"
    return ""


def parse_page(soup: BeautifulSoup, version: str) -> list[UnifiedEntry]:
    entries: list[UnifiedEntry] = []
    current_era = ""

    container = soup.find("div", class_="container")
    if not container:
        return entries

    for div in container.find_all("div", recursive=False):
        chart = div.find("div", class_="chart")
        if chart:
            comment = chart.find(string=lambda s: isinstance(s, Comment) and "LOC_ERA" in s)
            if comment:
                current_era = chart.find("h2", class_="civ-name").get_text(strip=True)  # type: ignore
                continue

        # Otherwise look for wonder entries
        for wonder_chart in div.find_all("div", class_="chart"):
            h2 = wonder_chart.find("h2", class_="civ-name")
            ps = wonder_chart.find_all("p", class_="civ-ability-desc")
            if not h2 or not ps:
                continue

            name = h2.get_text(separator=" ", strip=True)
            description = " ".join(p.get_text(separator=" ", strip=True) for p in ps)

            entries.append(
                UnifiedEntry(
                    section=Section.WORLDWONDER,
                    version=version,
                    name=name,
                    era=current_era,
                    description=description,
                )
            )

    return entries


def scrape_world_wonder():
    all_entries: list[UnifiedEntry] = []

    for version in Version:
        url = f"https://civ6bbg.github.io/en_US/{Section.WORLDWONDER}_{version}.html"
        response = requests.get(url)

        if not response.ok:
            print(f"WARNING: {url} not found (status {response.status_code})")
            continue

        print(f"Parsing {url}")
        soup = BeautifulSoup(response.content, "html.parser")

        page_entries = parse_page(soup, version=version)
        all_entries.extend(page_entries)

    print(f"\nTotal entries collected: {len(all_entries)}")
    return all_entries


if __name__ == "__main__":
    entries = scrape_world_wonder()
    print(entries[0])
