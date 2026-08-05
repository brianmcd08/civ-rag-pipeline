import re

import requests
from bs4 import BeautifulSoup, Comment

from src.config import Section, Version
from src.schema import UnifiedEntry


def get_civ_from_comment(chart) -> str:
    """Extract the feature category from the LOC comment preceding the h2."""

    # Matches e.g. "LOC_NAMED_DESERT_ACCONA_DESERT_NAME" -> "Desert"
    LOC_COMMENT_RE = re.compile(r"LOC_CIVILIZATION_([A-Z]+)_", re.IGNORECASE)

    for node in chart.children:
        if isinstance(node, Comment):
            m = LOC_COMMENT_RE.search(node)
            if m:
                return m.group(1).title()  # e.g. "AMERICA" -> "America"
    return ""


def parse_page(soup: BeautifulSoup, version: str) -> list[UnifiedEntry]:
    """
    Extract leaders.
    """

    entries: list[UnifiedEntry] = []

    for chart in soup.find_all("div", class_="base-game-text"):
        chart.decompose()

    items = soup.find_all(
        lambda tag: (  # type: ignore
            tag.name == "div"
            and "chart" in tag.get("class", [])
            and tag.find("h2", class_="civ-name")
            and tag.find("p", class_="civ-ability-desc")
        )
    )

    for item in items:
        item_name = item.find("h2", class_="civ-name").get_text(separator=" ", strip=True)
        item_descr = " ".join(
            [
                p.get_text(separator=" ", strip=True)
                for p in item.find_all("p", class_="civ-ability-desc")
            ]
        )

        civ = get_civ_from_comment(item)
        entries.append(
            UnifiedEntry(
                section=Section.LEADERS,  # what about bbg_expanded?
                version=version,
                name=item_name,
                description=item_descr,
                civilization=civ,
            )
        )

    print(f"\nTotal entries collected: {len(entries)}")
    return entries


def scrape_leaders() -> list[UnifiedEntry]:
    all_entries: list[UnifiedEntry] = []

    for version in Version:
        url = f"https://civ6bbg.github.io/en_US/{Section.LEADERS}_{version}.html"
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
    entries = scrape_leaders()
    print(entries[0])
