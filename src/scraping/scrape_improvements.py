import requests
from bs4 import BeautifulSoup

from src.config import Section, Version
from src.schema import UnifiedEntry


def scrape_improvements():
    entries: list[UnifiedEntry] = []
    for version in Version:
        url = f"https://civ6bbg.github.io/en_US/{Section.IMPROVEMENTS}_{version}.html"
        response = requests.get(url)
        if not response.ok:
            print(f"{url} not found and should be!")
            continue

        print(f"Parsing {url}")
        soup = BeautifulSoup(response.content, "html.parser")

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

            entries.append(
                UnifiedEntry(
                    section=Section.IMPROVEMENTS,
                    version=version,
                    name=item_name,
                    description=item_descr,
                )
            )

    print(f"\nTotal entries collected: {len(entries)}")
    return entries


if __name__ == "__main__":
    entries = scrape_improvements()
    print(entries[-1])
