"""Lossless handling of source characters unsupported by the XML parser.

Unsupported source bytes, forbidden XML 1.0 characters and invalid numeric
references are temporarily represented by valid private-use tokens. ElementTree
can then edit the document. ElementTree.write is wrapped once so those tokens are
restored byte-for-byte when the tree is saved. Structural XML errors are never
ignored or reconstructed.
"""
from __future__ import annotations

from pathlib import Path
import re
import app.backend.xml_backend as ET
_TOKEN_START = 0xF0000
_TOKEN_END = 0xFFFFD
_INVALID_REF = re.compile(r"&#(?:x([0-9A-Fa-f]+)|([0-9]+));")
_INVALID_REF_BYTES = re.compile(br"&#(?:x([0-9A-Fa-f]+)|([0-9]+));")
_INVALID_CONTROL_BYTES = re.compile(br"[\x00-\x08\x0b\x0c\x0e-\x1f]")
def _valid_xml_codepoint(value: int) -> bool:
    return (
        value in (0x9, 0xA, 0xD)
        or 0x20 <= value <= 0xD7FF
        or 0xE000 <= value <= 0xFFFD
        or 0x10000 <= value <= 0x10FFFF
    ) and value != 0xFFFD


def _tokenize_unsupported_bytes(raw: bytes) -> tuple[bytes, dict[str, bytes]]:
    """Fast path for the ASCII references/control bytes found in Anno XML."""
    preserved: dict[str, bytes] = {}
    counter = 0

    def token(value: bytes) -> bytes:
        nonlocal counter
        if _TOKEN_START + counter > _TOKEN_END:
            raise ValueError("Too many unsupported XML fragments to preserve.")
        placeholder = chr(_TOKEN_START + counter)
        counter += 1
        preserved[placeholder] = value
        return placeholder.encode("utf-8")

    def replace_reference(match):
        try:
            value = int(match.group(1), 16) if match.group(1) is not None else int(match.group(2), 10)
        except (TypeError, ValueError):
            return match.group(0)
        return match.group(0) if _valid_xml_codepoint(value) else token(match.group(0))

    masked = _INVALID_REF_BYTES.sub(replace_reference, raw)
    masked = _INVALID_CONTROL_BYTES.sub(lambda match: token(match.group(0)), masked)
    return masked, preserved


def _tokenize_unsupported(text: str) -> tuple[str, dict[str, bytes]]:
    """Replace parser-hostile source fragments with unique valid XML tokens."""
    preserved: dict[str, bytes] = {}
    counter = 0

    def token(raw: bytes) -> str:
        nonlocal counter
        if _TOKEN_START + counter > _TOKEN_END:
            raise ValueError("Too many unsupported XML fragments to preserve.")
        value = chr(_TOKEN_START + counter)
        counter += 1
        preserved[value] = raw
        return value

    def replace_reference(match):
        try:
            value = int(match.group(1), 16) if match.group(1) is not None else int(match.group(2), 10)
        except (TypeError, ValueError):
            return match.group(0)
        if _valid_xml_codepoint(value):
            return match.group(0)
        return token(match.group(0).encode("ascii"))

    text = _INVALID_REF.sub(replace_reference, text)
    result = []
    for char in text:
        codepoint = ord(char)
        if 0xDC80 <= codepoint <= 0xDCFF:
            # Produced by UTF-8 surrogateescape: preserve the exact original byte.
            result.append(token(bytes((codepoint - 0xDC00,))))
        elif _valid_xml_codepoint(codepoint):
            result.append(char)
        else:
            result.append(token(char.encode("utf-8", errors="surrogatepass")))
    return "".join(result), preserved


def sanitize_xml_text(text: str) -> tuple[str, int]:
    """Compatibility API: mask unsupported content without deleting it."""
    masked, preserved = _tokenize_unsupported(text)
    return masked, len(preserved)


def parse_xml_tolerant(path):
    """Parse XML while preserving parser-hostile original content losslessly."""
    path = Path(path)
    raw = path.read_bytes()

    # Anno XML commonly contains invalid numeric references inside otherwise
    # valid UTF-8. Mask them before parsing. This avoids one failed full parse
    # and avoids walking very large HeightMap/terrain text character by character.
    masked_bytes, preserved = (raw, {})
    if b"&#" in raw:
        masked_bytes, preserved = _tokenize_unsupported_bytes(raw)
    if preserved:
        try:
            root = ET.fromstring(masked_bytes)
        except (ET.ParseError, OSError):
            # Continue with the general encoding-aware fallback below.
            pass
        else:
            tree = ET.ElementTree(root)
            tree._xml_preserved_tokens = preserved
            tree._xml_source_encoding = "bytes"
            return tree, True, len(preserved)

    try:
        return ET.parse(path), False, 0
    except (ET.ParseError, OSError) as original_error:
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            encoding = "utf-16"
            text = raw.decode(encoding, errors="surrogatepass")
        elif raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
            text = raw.decode(encoding, errors="surrogateescape")
        else:
            encoding = "utf-8"
            text = raw.decode(encoding, errors="surrogateescape")
        masked, preserved = _tokenize_unsupported(text)
        if not preserved:
            raise original_error
        try:
            root = ET.fromstring(masked)
        except (ET.ParseError, OSError):
            raise original_error
        tree = ET.ElementTree(root)
        tree._xml_preserved_tokens = preserved
        tree._xml_source_encoding = encoding
        return tree, True, len(preserved)
