import requests
from bs4 import BeautifulSoup

from src.config import Section, Version
from src.schema import UnifiedEntry


def parse_page(soup: BeautifulSoup, version: str) -> list[UnifiedEntry]:
    """
    Extract governors.
    """

    entries: list[UnifiedEntry] = []

    items = soup.find_all(
        lambda tag: (  # type: ignore
            tag.name == "div"
            and "chart" in tag.get("class", [])
            and tag.find("h2", class_="civ-name")
            and tag.find("h3", class_="civ-ability-name")
            and tag.find("p", class_="civ-ability-desc")
        )
    )

    for item in items:
        item_name = item.find("h2", class_="civ-name").get_text(separator=" ", strip=True)

        item_descr1 = " ".join(
            [
                p.get_text(separator=" ", strip=True)
                for p in item.find_all(["h3"], class_="civ-ability-name")
            ]
        )

        item_descr2 = " ".join(
            [
                p.get_text(separator=" ", strip=True)
                for p in item.find_all(["p"], class_="civ-ability-desc")
            ]
        )

        item_descr = f"{item_descr1} {item_descr2}"

        entries.append(
            UnifiedEntry(
                section=Section.GOVERNORS,
                version=version,
                name=item_name,
                description=item_descr,
            )
        )

    print(f"\nTotal entries collected: {len(entries)}")
    return entries


def scrape_governor():
    all_entries: list[UnifiedEntry] = []

    for version in Version:
        url = f"https://civ6bbg.github.io/en_US/{Section.GOVERNORS}_{version}.html"
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
    entries = scrape_governor()
    print(entries[-1])
