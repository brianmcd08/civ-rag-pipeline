import requests
from bs4 import BeautifulSoup

from src.config import Section, Version
from src.schema import UnifiedEntry


def parse_page(soup: BeautifulSoup, version: str) -> list[UnifiedEntry]:
    """
    Walk all div.row elements in order, tracking the current great person type
    and era, then collect individuals from non-header rows beneath them.
    """

    entries: list[UnifiedEntry] = []
    current_type = ""
    current_era = ""

    container = soup.find("div", class_="container")
    if not container:
        return entries

    for row in container.find_all("div", class_="row", recursive=False):
        charts = row.find_all("div", class_="chart")

        # --- Great person type header row ---
        # Has exactly one chart with an h2.civ-name and no ability-desc
        h2 = charts[0].find("h2", class_="civ-name") if len(charts) == 1 else None
        if h2 and not charts[0].find("p", class_="civ-ability-desc"):
            # get_text strips the image; grab first two words e.g. "Great General"
            current_type = " ".join(h2.get_text(separator=" ", strip=True).split()[:2])
            current_era = ""  # reset era when type changes
            continue

        # --- Era sub-header row ---
        # Has exactly one chart with an h3.civ-name and no ability-desc
        h3 = charts[0].find("h3", class_="civ-name") if len(charts) == 1 else None
        if h3 and not charts[0].find("p", class_="civ-ability-desc"):
            current_era = h3.get_text(separator=" ", strip=True)
            continue

        # --- Individual person row ---
        for chart in charts:
            ability_names = chart.find_all("p", class_="civ-ability-name")
            ability_descs = chart.find_all("p", class_="civ-ability-desc")

            if not ability_names or not ability_descs:
                continue

            # First p.civ-ability-name = person name, second = charges
            person_name = ability_names[0].get_text(separator=" ", strip=True)
            charges_raw = (
                ability_names[1].get_text(separator=" ", strip=True)
                if len(ability_names) > 1
                else ""
            )
            # charges text looks like "1 " after stripping the img — keep just the digit
            charges = charges_raw.split()[0] if charges_raw else ""

            description = " ".join(p.get_text(separator=" ", strip=True) for p in ability_descs)

            entries.append(
                UnifiedEntry(
                    section=Section.GREATPEOPLE,
                    version=version,
                    great_person_type=current_type,
                    era=current_era,
                    name=person_name,
                    charges=charges,
                    description=description,
                )
            )

    return entries


def scrape_great_people():
    all_entries: list[UnifiedEntry] = []

    for version in Version:
        url = f"https://civ6bbg.github.io/en_US/{Section.GREATPEOPLE}_{version}.html"
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
    scrape_great_people()
