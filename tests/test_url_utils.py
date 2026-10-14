from bs4 import BeautifulSoup

from scripts.url_utils import url_has_host, url_hostname
from scripts.utilities.fix_accessibility import AccessibilityFixer


def test_url_helpers_distinguish_authorized_hosts_from_host_lookalikes():
    assert not url_has_host("https://evil.test/?next=ror.org", "ror.org")
    assert not url_has_host("https://ror.org.evil.test/", "ror.org")


def test_url_hostname_accepts_http_urls_and_protocol_relative_urls():
    assert url_hostname("https://Example.org:8443/path") == "example.org"
    assert url_hostname("//sub.example.org/path") == "sub.example.org"


def test_url_has_host_accepts_exact_hosts_and_subdomains():
    assert url_has_host("https://ror.org/03yrm5c26", "ror.org")
    assert url_has_host("https://qlever.scholia.wiki/author/Q1", "scholia.wiki")


def test_url_has_host_rejects_hostnames_in_paths_and_untrusted_suffixes():
    assert not url_has_host("https://attacker.test/ror.org", "ror.org")
    assert not url_has_host("https://ror.org.attacker.test/", "ror.org")
    assert not url_has_host("https://attacker-ror.org/", "ror.org")


def test_url_hostname_rejects_non_web_schemes_and_malformed_hosts():
    assert url_hostname("javascript://ror.org/alert(1)") is None
    assert url_hostname("https://[broken") is None


def test_accessibility_labels_match_link_hosts_not_arbitrary_substrings():
    fixer = object.__new__(AccessibilityFixer)
    trusted = BeautifulSoup('<a href="https://github.com/user">', "html.parser").a
    spoofed = BeautifulSoup(
        '<a href="https://attacker.test/path/github.com">',
        "html.parser",
    ).a

    assert fixer._generate_link_label(trusted) == "GitHub profile"
    assert fixer._generate_link_label(spoofed) == ""


def test_iframe_labels_match_service_hosts_not_arbitrary_substrings():
    fixer = object.__new__(AccessibilityFixer)
    trusted = BeautifulSoup(
        '<iframe src="https://qlever.scholia.wiki/work/Q1"></iframe>',
        "html.parser",
    ).iframe
    spoofed = BeautifulSoup(
        '<iframe src="https://attacker.test/scholia"></iframe>',
        "html.parser",
    ).iframe

    assert fixer._generate_iframe_title(trusted) == (
        "Interactive data visualization from Wikidata"
    )
    assert fixer._generate_iframe_title(spoofed) == "Embedded content"
