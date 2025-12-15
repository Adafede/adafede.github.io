"""
CiTO citation merger.

Merges multiple CiTO citation dictionaries into a single unified dictionary.
Used to combine citations from multiple QMD files.
"""

from collections import defaultdict
from typing import Dict, Iterable, Set


def merge_citos(cito_dicts: Iterable[Dict[str, Set[str]]]) -> Dict[str, Set[str]]:
    """Merge multiple CiTO citation dictionaries.

    Args:
        cito_dicts: Iterable of dictionaries mapping citation IDs to sets of properties

    Returns:
        Merged dictionary with all unique citations and their combined properties

    Example:
        >>> dict1 = {'smith2020': {'citesAsEvidence'}}
        >>> dict2 = {'smith2020': {'supports'}, 'jones2021': {'citation'}}
        >>> merge_citos([dict1, dict2])
        {'smith2020': {'citesAsEvidence', 'supports'}, 'jones2021': {'citation'}}
    """
    merged: Dict[str, Set[str]] = defaultdict(set)

    for cito_dict in cito_dicts:
        for cite_id, properties in cito_dict.items():
            merged[cite_id].update(properties)

    return dict(merged)


if __name__ == "__main__":
    # Example usage / test
    dict1 = {"smith2020": {"citesAsEvidence", "supports"}}
    dict2 = {"smith2020": {"usesDataFrom"}, "jones2021": {"citation"}}
    dict3 = {"brown2019": {"citesAsAuthority"}}

    result = merge_citos([dict1, dict2, dict3])

    print("Merged citations:")
    for cite_id, props in sorted(result.items()):
        print(f"  {cite_id}: {', '.join(sorted(props))}")
