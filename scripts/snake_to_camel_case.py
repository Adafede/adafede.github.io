"""
Snake case to camel case converter.

Converts snake_case strings to camelCase strings.
Used for CiTO property name transformation.
"""


def snake_to_camel_case(snake_str: str) -> str:
    """Convert snake_case string to camelCase.

    Args:
        snake_str: String in snake_case format

    Returns:
        String in camelCase format

    Examples:
        >>> snake_to_camel_case("cites_as_evidence")
        'citesAsEvidence'
        >>> snake_to_camel_case("uses_data_from")
        'usesDataFrom'
        >>> snake_to_camel_case("cites")
        'cites'
        >>> snake_to_camel_case("")
        ''
    """
    if not snake_str:
        return snake_str

    components = snake_str.split("_")
    # First component stays lowercase, rest are capitalized
    return components[0] + "".join(word.capitalize() for word in components[1:])


if __name__ == "__main__":
    # Run doctests
    import doctest

    doctest.testmod()

    # Demo
    test_cases = [
        "cites_as_evidence",
        "uses_data_from",
        "cites_as_authority",
        "supports",
        "cites",
    ]

    print("Snake case to camel case conversion:")
    for test in test_cases:
        print(f"  {test:25s} -> {snake_to_camel_case(test)}")
