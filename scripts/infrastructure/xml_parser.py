"""Typed wrapper around the untyped `lxml` library.

lxml ships without type stubs. This module provides a structurally-typed
interface (`XmlElement`) and casts lxml's runtime objects at the boundary,
so the rest of the codebase can rely on real static types instead of `Any`.
"""

from __future__ import annotations

from typing import Protocol, cast
from xml.etree.ElementTree import ParseError as XmlParseError


# Typed interface for lxml.etree module
class ParsedTree(Protocol):
    def getroot(self) -> object: ...


class ElementTreeInstance(Protocol):
    def write(self, path: str, **kwargs: object) -> None: ...


class ElementTreeClass(Protocol):
    def __call__(self, element: object) -> ElementTreeInstance: ...


class EtreeModule(Protocol):
    def fromstring(self, content: bytes | str) -> object: ...
    def parse(self, source: object, parser: object = ...) -> ParsedTree: ...
    def XMLParser(self, *args: object, **kwargs: object) -> object: ...
    def CDATA(self, content: str) -> object: ...

    ElementTree: ElementTreeClass


# Import lxml and cast to typed interface
import lxml.etree as _lxml_etree

_etree: EtreeModule = cast(EtreeModule, _lxml_etree)


class XmlElement(Protocol):
    """Structural type for an lxml element node."""

    text: str | None

    def find(self, path: str) -> XmlElement | None: ...
    def findall(self, path: str) -> list[XmlElement]: ...
    def get(self, key: str, default: str = "") -> str: ...
    def clear(self) -> None: ...

    def append(self, element: object) -> None: ...


class XmlParser:
    """Thin, typed facade over ``lxml.etree``."""

    ParseError: type[XmlParseError] = XmlParseError

    @staticmethod
    def fromstring(content: bytes | str) -> XmlElement:
        """Parse XML bytes/str into a typed element."""
        return cast(XmlElement, _etree.fromstring(content))

    @staticmethod
    def parse(source: object, parser: object | None = None) -> XmlElement:
        """Parse an XML document from a file-like object."""
        if parser is None:
            return cast(XmlElement, _etree.parse(source).getroot())
        return cast(XmlElement, _etree.parse(source, parser=parser).getroot())

    @staticmethod
    def new_parser(
        recover: bool = True,
        resolve_entities: bool = False,
        remove_blank_text: bool = False,
    ) -> object:
        """Create a lenient lxml XMLParser instance."""
        return _etree.XMLParser(
            recover=recover,
            resolve_entities=resolve_entities,
            remove_blank_text=remove_blank_text,
        )

    @staticmethod
    def cdata(content: str) -> object:
        """Create an lxml CDATA section."""
        return _etree.CDATA(content)

    @staticmethod
    def write(
        element: object,
        path: str,
        pretty_print: bool = True,
        encoding: str = "utf-8",
        xml_declaration: bool = True,
    ) -> None:
        """Write an lxml element tree to a file."""
        _etree.ElementTree(element).write(
            path,
            pretty_print=pretty_print,
            encoding=encoding,
            xml_declaration=xml_declaration,
        )
