import hashlib
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from src.config import Section, Version


class ParsedQuery(BaseModel):
    """
    Cleaned data after raw input from user
    """

    cleaned_query: str = Field(
        description="User query after typos, fillers removed",
        min_length=5,
        max_length=128,
    )

    version: Version | None = Field(
        description="Extracted version from the query",
        default=Version.get_latest_version(),
    )

    @field_validator("version", mode="before")
    @classmethod
    def parse_null_version(cls, v):
        if v == "null" or v == "none" or v == "None":
            return None
        return v


class RoutingDecision(BaseModel):
    section_hints: list[Section] | None = Field(
        description="The BBG section(s) most relevant to this query",
        default=None,
    )

    @field_validator("section_hints", mode="before")
    @classmethod
    def parse_null_section(cls, v):
        if v == "null" or v == "none" or v == "None":
            return None
        return v


@dataclass
class UnifiedEntry:
    """
    For storing data from all ingestion runs
    """

    section: Section  # page name
    version: str  # bbg version

    name: str | None = (
        None  # e.g. "Accona Desert" or individual person name, e.g. "Boudica"
    )
    category: str | None = (
        None  # e.g. "Desert", "Mountain", "River" or top-level h1 section e.g. "Game Mechanics", "Leaders"
    )
    subcategory: str | None = None  # h2 section e.g. "Global Changes", "Combat"

    civilization: str | None = None
    description: str | None = None

    great_person_type: str | None = None  # e.g. "Great General", "Great Scientist"
    era: str | None = None  # e.g. "Classical Era"
    charges: str | None = None  # e.g. "1", "2"

    def generate_embedding_text(self) -> str:
        """
        Build a rich embedding string that includes all meaningful context fields.

        Every field that carries semantic meaning is included so the embedding
        model has enough signal to surface this chunk for relevant queries.
        Previously only section + version + name + description were included,
        leaving civilization, category, subcategory, great_person_type, and era
        invisible to the vector search.

        Returns:
            str: combined text for embedding
        """
        parts: list[str] = [str(self.section)]

        # Great people context — type and era come BEFORE the name so the
        # embedding reads "Great General Classical Era Sun Tzu: ..." which
        # gives the model enough context even when the description is short.
        if self.great_person_type:
            parts.append(self.great_person_type)
        if self.era:
            parts.append(self.era)

        # Category/subcategory — important for changelog and misc entries where
        # the description alone is a bare bullet point with no surrounding context.
        if self.category:
            parts.append(self.category)
        if self.subcategory:
            parts.append(self.subcategory)

        if self.name:
            parts.append(f"{self.name}:")

        if self.description:
            parts.append(self.description)

        # Civilization — critical for the names section where the description is
        # empty and the only useful fact IS which civ this name belongs to.
        if self.civilization:
            parts.append(f"Civilizations: {self.civilization}")

        return " ".join(parts)

    def generate_metadata(self) -> dict[str, str]:
        """
        Combine version, category, subcategory, civilization,
            great person type, era, and charges

        Returns:
            dict[str, str]
        """
        return {
            k: v
            for k, v in {
                "section": self.section,
                "bbg_version": [self.version],
                "category": self.category,
                "subcategory": self.subcategory,
                "civilization": self.civilization,
                "great_person_type": self.great_person_type,
                "era": self.era,
                "charges": self.charges,
            }.items()
            if v is not None
        }

    def generate_hash(self) -> str:
        hash_obj = hashlib.sha256()
        hash_str = self.section + (self.name or "") + (self.description or "")
        hash_obj.update(hash_str.encode("utf-8"))
        return hash_obj.hexdigest()
