from scripts.site.migrate_posts import convert_span_attributes


def test_convert_span_attributes_keeps_rdfa_on_non_link_span():
    body = '[metabolomics]{about="wd:Q12149006"}'

    assert convert_span_attributes(body) == (
        '<span about="wd:Q12149006">metabolomics</span>'
    )
