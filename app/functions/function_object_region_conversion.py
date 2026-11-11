"""Plan safe, region-based RD3D object conversions for Object Easy Mode."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Sequence

REGION_CATEGORY_TOKENS = {
    "Old World": "moderate",
    "New World": "jungle",
    "Enbesa": "enbesa",
    "Arctic": "arctic",
}
_REGION_TOKENS = frozenset(REGION_CATEGORY_TOKENS.values())
_GENERIC_WORDS = frozenset({"dry", "snow", "ice", "no", "skirt"})
_SIZE_WORDS = ("very large", "large", "medium", "small", "big")


@dataclass(frozen=True)
class RegionConversion:
    """One proposed RD3D object-path replacement."""

    row_index: int
    source_path: str
    target_path: str
    source_category: str
    target_category: str
    status: str


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def category_region(category: str) -> str | None:
    """Return the configured display region encoded in a category name."""
    words = _words(category)
    for region, token in REGION_CATEGORY_TOKENS.items():
        if token in words:
            return region
    return None


def _family(category: str) -> str:
    words = list(re.findall(r"[a-z0-9]+", str(category or "").casefold()))
    return words[0] if words else ""


def _size_hint(category: str, path: str = "") -> str:
    text = f"{category} {path}".casefold().replace("_", " ")
    for size in _SIZE_WORDS:
        if re.search(rf"\b{re.escape(size)}\b", text):
            return "large" if size in {"big", "very large"} else size
    return ""


def _category_score(source: str, candidate: str, source_path: str) -> tuple[int, int, str]:
    source_words = _words(source) - _REGION_TOKENS - _GENERIC_WORDS
    candidate_words = _words(candidate) - _REGION_TOKENS - _GENERIC_WORDS
    if not source_words or _family(source) != _family(candidate):
        return (-10_000, 0, candidate.casefold())
    overlap = len(source_words & candidate_words)
    missing = len(source_words - candidate_words)
    extra = len(candidate_words - source_words)
    score = overlap * 30 - missing * 12 - extra * 4
    source_size = _size_hint(source, source_path)
    candidate_size = _size_hint(candidate)
    if source_size:
        score += 35 if candidate_size == source_size else -10
    # Generic trees should become a natural regional tree rather than a dead tree.
    if _family(source) == "tree":
        source_dead = bool({"dead", "stumps", "burned"} & _words(source))
        candidate_dead = bool({"dead", "stumps", "burned"} & _words(candidate))
        score += 25 if source_dead == candidate_dead else -80
        if not source_dead and "acacia" in _words(candidate):
            score += 18
    return (score, overlap, candidate.casefold())


def find_target_category(
    source_category: str,
    source_path: str,
    target_region: str,
    categories: Mapping[str, Sequence[str]],
) -> str | None:
    """Find the closest same-family category in the requested target region."""
    token = REGION_CATEGORY_TOKENS.get(target_region)
    if token is None:
        raise ValueError(f"Unsupported target region: {target_region}")
    candidates = [
        category for category in categories
        if token in _words(category) and _family(category) == _family(source_category)
    ]
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda candidate: _category_score(source_category, candidate, source_path),
        reverse=True,
    )
    best = ranked[0]
    return best if _category_score(source_category, best, source_path)[0] > -100 else None


def _file_number(path: str) -> int | None:
    match = re.search(r"(\d+)(?!.*\d)", str(path or ""))
    return int(match.group(1)) if match else None


def choose_target_path(
    source_path: str,
    targets: Sequence[str],
    used_paths: set[str],
    mode: str,
) -> str | None:
    """Choose a deterministic target while preserving variants where possible."""
    if not targets:
        return None
    source_number = _file_number(source_path)
    numbered = [(target, _file_number(target)) for target in targets]
    exact = [target for target, number in numbered if source_number is not None and number == source_number]
    ordered = exact + [target for target in targets if target not in exact]
    if mode == "Avoid duplicates":
        unused = [target for target in ordered if target not in used_paths]
        if unused:
            ordered = unused
    target = ordered[0]
    used_paths.add(target)
    return target


def plan_region_conversion(
    rows: Iterable[tuple[int, str]],
    target_region: str,
    categories: Mapping[str, Sequence[str]],
    category_for_object,
    mode: str = "Preserve if possible",
) -> tuple[list[RegionConversion], Counter]:
    """Create a non-mutating conversion plan and aggregate result statistics."""
    changes: list[RegionConversion] = []
    stats = Counter(scanned=0, changed=0, already_matching=0, no_mapping=0, neutral=0)
    used_by_category: dict[str, set[str]] = defaultdict(set)
    target_token = REGION_CATEGORY_TOKENS.get(target_region)
    if target_token is None:
        raise ValueError(f"Unsupported target region: {target_region}")

    for row_index, source_path in rows:
        stats["scanned"] += 1
        source_category = category_for_object(source_path)
        source_region = category_region(source_category)
        if source_region == target_region:
            stats["already_matching"] += 1
            continue
        if source_region is None:
            stats["neutral"] += 1
            continue
        target_category = find_target_category(
            source_category, source_path, target_region, categories,
        )
        targets = tuple(categories.get(target_category, ())) if target_category else ()
        target_path = choose_target_path(
            source_path, targets, used_by_category[target_category or ""], mode,
        )
        if not target_category or not target_path:
            stats["no_mapping"] += 1
            continue
        status = "Exact variant" if _file_number(source_path) == _file_number(target_path) else "Variant fallback"
        changes.append(RegionConversion(
            row_index=row_index,
            source_path=source_path,
            target_path=target_path,
            source_category=source_category,
            target_category=target_category,
            status=status,
        ))
        stats["changed"] += 1
    return changes, stats
