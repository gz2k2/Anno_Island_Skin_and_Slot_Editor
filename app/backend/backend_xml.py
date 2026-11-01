"""Central lxml backend with the ElementTree API used by the application.

The adapter keeps legacy call sites stable, accepts ElementTree's
short_empty_elements argument, enables huge-tree parsing for Anno map arrays,
and carries lossless unsupported-content metadata with document copies.
"""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path
from lxml import etree as _ET

ParseError = _ET.XMLSyntaxError
XMLSyntaxError = _ET.XMLSyntaxError
Element = _ET.Element
SubElement = _ET.SubElement
TreeBuilder = _ET.TreeBuilder
indent = _ET.indent


def XMLParser(*args, **kwargs):
    kwargs.setdefault("huge_tree", True)
    kwargs.setdefault("recover", False)
    kwargs.setdefault("resolve_entities", False)
    kwargs.setdefault("no_network", True)
    kwargs.setdefault("remove_comments", True)
    kwargs.setdefault("remove_pis", True)
    return _ET.XMLParser(*args, **kwargs)


def _parser():
    return XMLParser()


class ElementTree:
    """Small metadata-capable wrapper around lxml.etree._ElementTree."""

    def __init__(self, element=None, *, _tree=None):
        if _tree is not None:
            self._tree = _tree
        elif isinstance(element, ElementTree):
            self._tree = _ET.ElementTree(element.getroot())
        elif isinstance(element, _ET._ElementTree):
            self._tree = element
        else:
            self._tree = _ET.ElementTree(element)
        self._xml_preserved_tokens = {}
        self._xml_source_encoding = None

    def getroot(self):
        return self._tree.getroot()

    def _setroot(self, element):
        return self._tree._setroot(element)

    def find(self, *args, **kwargs):
        return self._tree.find(*args, **kwargs)

    def findall(self, *args, **kwargs):
        return self._tree.findall(*args, **kwargs)

    def findtext(self, *args, **kwargs):
        return self._tree.findtext(*args, **kwargs)

    def iter(self, *args, **kwargs):
        return self._tree.iter(*args, **kwargs)

    def xpath(self, *args, **kwargs):
        return self._tree.xpath(*args, **kwargs)

    def write(self, file_or_filename, encoding="us-ascii", xml_declaration=None,
              default_namespace=None, method="xml", *, short_empty_elements=True,
              pretty_print=False):
        del short_empty_elements  # lxml always uses compact empty-element syntax.
        if default_namespace is not None:
            raise ValueError("default_namespace is not supported by the lxml backend")
        output_encoding = "utf-8" if encoding in (None, "unicode") else encoding
        data = _ET.tostring(
            self._tree,
            encoding=output_encoding,
            xml_declaration=xml_declaration,
            method=method,
            pretty_print=pretty_print,
        )
        for placeholder, original in self._xml_preserved_tokens.items():
            data = data.replace(placeholder.encode("utf-8"), original)
        if hasattr(file_or_filename, "write"):
            file_or_filename.write(data)
        else:
            Path(file_or_filename).write_bytes(data)

    def __deepcopy__(self, memo):
        copied = type(self)(_tree=deepcopy(self._tree, memo))
        copied._xml_preserved_tokens = deepcopy(self._xml_preserved_tokens, memo)
        copied._xml_source_encoding = self._xml_source_encoding
        return copied

    def __getattr__(self, name):
        return getattr(self._tree, name)


def parse(source, parser=None):
    # libxml2's filename reader is disproportionately slow on Anno files with
    # very large text nodes. Reading bytes in Python and parsing from memory is
    # substantially faster for the supplied 30-97 MB map XML files.
    data = Path(source).read_bytes()
    root = _ET.fromstring(data, parser or _parser())
    return ElementTree(root)


def fromstring(text, parser=None):
    if isinstance(text, str):
        text = text.encode("utf-8")
    return _ET.fromstring(text, parser or _parser())


def tostring(element, encoding="us-ascii", method="xml", *,
             xml_declaration=None, default_namespace=None,
             short_empty_elements=True, pretty_print=False):
    del short_empty_elements
    if default_namespace is not None:
        raise ValueError("default_namespace is not supported by the lxml backend")
    target = element._tree if isinstance(element, ElementTree) else element
    return _ET.tostring(
        target,
        encoding=encoding,
        method=method,
        xml_declaration=xml_declaration,
        pretty_print=pretty_print,
    )


def iterparse(source, events=("end",), tag=None, **kwargs):
    kwargs.setdefault("huge_tree", True)
    kwargs.setdefault("recover", False)
    kwargs.setdefault("resolve_entities", False)
    kwargs.setdefault("no_network", True)
    return _ET.iterparse(str(source), events=events, tag=tag, **kwargs)
