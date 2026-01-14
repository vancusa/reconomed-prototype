"""openEHR composition builder for consultation payloads.

Example:
    >>> template = {
    ...     "sections": [
    ...         {
    ...             "section_id": "chief_complaint",
    ...             "fields": [
    ...                 {
    ...                     "field_id": "complaint_description",
    ...                     "field_type": "text",
    ...                     "openehr_archetype": "openEHR-EHR-OBSERVATION.story.v1",
    ...                     "openehr_path": "/data/events/any_event/data/items[complaint]",
    ...                 }
    ...             ],
    ...         }
    ...     ]
    ... }
    >>> data = {"chief_complaint": {"complaint_description": "Headache"}}
    >>> build_composition(template, data, {"consultation_id": "c1", "specialty": "internal_medicine"})
    {'language': 'ro', 'territory': 'RO', 'category': 'event', 'context': {'consultation_id': 'c1', 'specialty': 'internal_medicine'}, 'content': [{'archetype': 'openEHR-EHR-OBSERVATION.story.v1', 'data': {'data': {'events': {'any_event': {'data': {'items': {'complaint': 'Headache'}}}}}}}]}
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable
import re


PATH_PART_PATTERN = re.compile(r"^(?P<name>[^\[]+)(?:\[(?P<key>.+)\])?$")


def build_composition(template: Dict[str, Any], structured_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a composition-like payload using relative openEHR paths.
    """
    language = context.get("language") or "ro"
    territory = context.get("territory") or "RO"
    category = context.get("category") or "event"

    composition_context = {
        key: _normalize_context_value(value)
        for key, value in context.items()
        if value is not None and key not in {"language", "territory", "category"}
    }

    entries: Dict[str, Dict[str, Any]] = {}

    for section in template.get("sections", []):
        section_id = section.get("section_id")
        section_values = structured_data.get(section_id, {}) if section_id else {}
        for field in section.get("fields", []):
            archetype = field.get("openehr_archetype")
            path = field.get("openehr_path")
            if not archetype or not path:
                continue

            field_id = field.get("field_id")
            value = section_values.get(field_id) if field_id else None
            if _is_empty(value):
                continue

            value = _normalize_value(field.get("field_type"), value)
            entry_data = entries.setdefault(archetype, {})
            _apply_relative_path(entry_data, path, value)

    content = [
        {"archetype": archetype, "data": data}
        for archetype, data in sorted(entries.items(), key=lambda item: item[0])
    ]

    return {
        "language": language,
        "territory": territory,
        "category": category,
        "context": composition_context,
        "content": content,
    }


def _apply_relative_path(target: Dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split("/") if part]
    current = target

    for index, part in enumerate(parts):
        match = PATH_PART_PATTERN.match(part)
        if not match:
            key = part
            nested_key = None
        else:
            key = match.group("name")
            nested_key = match.group("key")

        is_last = index == len(parts) - 1
        if nested_key is not None:
            current = _ensure_mapping(current, key)
            if is_last:
                current[nested_key] = value
                return
            current = _ensure_mapping(current, nested_key)
            continue

        if is_last:
            current[key] = value
            return
        current = _ensure_mapping(current, key)


def _ensure_mapping(container: Dict[str, Any], key: str) -> Dict[str, Any]:
    existing = container.get(key)
    if not isinstance(existing, dict):
        container[key] = {}
    return container[key]


def _normalize_value(field_type: str | None, value: Any) -> Any:
    if field_type in {"number", "quantity"}:
        return _normalize_number(value)
    if field_type == "date":
        return _normalize_date(value)
    return value


def _normalize_context_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _normalize_number(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return value
    return value


def _normalize_date(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return datetime.fromisoformat(text).isoformat()
        except ValueError:
            return value
    return value


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, dict):
        return len(value) == 0
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        try:
            return len(value) == 0
        except TypeError:
            return False
    return False
