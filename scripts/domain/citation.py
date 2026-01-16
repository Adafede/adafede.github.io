"""Citation domain models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CitoProperty(str, Enum):
    """CiTO (Citation Typing Ontology) property types.

    See: http://purl.org/spar/cito/
    """

    # Default
    CITATION = "citation"

    # Factual relations
    CITES = "cites"
    CITES_AS_AUTHORITY = "cites_as_authority"
    CITES_AS_EVIDENCE = "cites_as_evidence"
    CITES_AS_METADATA_DOCUMENT = "cites_as_metadata_document"
    CITES_AS_RECOMMENDED_READING = "cites_as_recommended_reading"
    CITES_AS_RELATED = "cites_as_related"
    CITES_AS_SOURCE_DOCUMENT = "cites_as_source_document"
    CITES_FOR_INFORMATION = "cites_for_information"

    # Data relations
    USES_DATA_FROM = "uses_data_from"
    USES_METHOD_IN = "uses_method_in"

    # Rhetorical relations
    AGREES_WITH = "agrees_with"
    DISAGREES_WITH = "disagrees_with"
    DISPUTES = "disputes"
    SUPPORTS = "supports"
    CONFIRMS = "confirms"
    REFUTES = "refutes"
    EXTENDS = "extends"
    UPDATES = "updates"
    REVIEWS = "reviews"

    # Other
    DISCUSSES = "discusses"
    OBTAINS_BACKGROUND_FROM = "obtains_background_from"

    def to_camel_case(self) -> str:
        """Convert snake_case property to camelCase for CiTO ontology.

        Returns:
            camelCase version of the property
        """
        parts = self.value.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])


@dataclass(frozen=True)
class Citation:
    """Represents a citation to a scholarly work."""

    cite_id: str
    properties: set[CitoProperty] = field(default_factory=set)

    def __post_init__(self):
        """Ensure properties is a set."""
        if not isinstance(self.properties, set):
            object.__setattr__(self, "properties", set(self.properties))

    @classmethod
    def from_dict(cls, cite_id: str, properties: set[str]) -> "Citation":
        """Create Citation from string properties.

        Args:
            cite_id: Citation identifier
            properties: Set of property names as strings

        Returns:
            Citation instance
        """
        cito_props = {
            CitoProperty(prop)
            if prop in CitoProperty.__members__.values()
            else CitoProperty.CITATION
            for prop in properties
        }
        return cls(cite_id=cite_id, properties=cito_props)

    def add_property(self, prop: CitoProperty) -> "Citation":
        """Add a property to this citation (returns new instance).

        Args:
            prop: CiTO property to add

        Returns:
            New Citation with added property
        """
        new_props = self.properties | {prop}
        return Citation(cite_id=self.cite_id, properties=new_props)

    def merge_with(self, other: "Citation") -> "Citation":
        """Merge with another citation (union of properties).

        Args:
            other: Another citation with the same cite_id

        Returns:
            New Citation with merged properties

        Raises:
            ValueError: If cite_ids don't match
        """
        if self.cite_id != other.cite_id:
            raise ValueError(
                f"Cannot merge citations with different IDs: "
                f"{self.cite_id} != {other.cite_id}",
            )

        merged_props = self.properties | other.properties
        return Citation(cite_id=self.cite_id, properties=merged_props)

    def to_annotation_string(self) -> str:
        """Generate CiTO annotation string for HTML injection.

        Returns:
            String like "[cito:citesAsEvidence] [cito:supports]"
        """
        camel_props = [prop.to_camel_case() for prop in sorted(self.properties)]
        return " ".join(f"[cito:{prop}]" for prop in camel_props)

    @property
    def sorted_properties(self) -> list[str]:
        """Get properties as sorted list of strings.

        Returns:
            Sorted list of property names
        """
        return sorted(prop.value for prop in self.properties)


@dataclass
class CitationRegistry:
    """Registry of all citations in a document or collection."""

    citations: dict[str, Citation] = field(default_factory=dict)

    def add_citation(self, citation: Citation) -> None:
        """Add or merge a citation into the registry.

        Args:
            citation: Citation to add
        """
        if citation.cite_id in self.citations:
            existing = self.citations[citation.cite_id]
            self.citations[citation.cite_id] = existing.merge_with(citation)
        else:
            self.citations[citation.cite_id] = citation

    def get_citation(self, cite_id: str) -> Optional[Citation]:
        """Get citation by ID.

        Args:
            cite_id: Citation identifier

        Returns:
            Citation or None if not found
        """
        return self.citations.get(cite_id)

    def merge_from_dict(self, cito_dict: dict[str, set[str]]) -> None:
        """Merge citations from dictionary format.

        Args:
            cito_dict: Dictionary mapping cite_id -> set of property strings
        """
        for cite_id, props in cito_dict.items():
            citation = Citation.from_dict(cite_id, props)
            self.add_citation(citation)

    def to_dict(self) -> dict[str, list[str]]:
        """Export as dictionary with sorted property lists.

        Returns:
            Dictionary mapping cite_id -> sorted list of properties
        """
        return {
            cite_id: citation.sorted_properties
            for cite_id, citation in self.citations.items()
        }
