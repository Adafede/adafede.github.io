from commonmeta import encode_doi


def make_doi() -> str:
    doi_url = encode_doi("10.59350")
    return doi_url.removeprefix("https://doi.org/")
