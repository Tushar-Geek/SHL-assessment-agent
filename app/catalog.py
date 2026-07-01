from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.models import Assessment

logger = logging.getLogger(__name__)


class CatalogRepository:
    def __init__(self, catalog_path: Path):
        self.catalog_path = catalog_path
        self._items: list[Assessment] | None = None

    def load(self) -> list[Assessment]:
        if self._items is not None:
            return self._items
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Catalog file not found: {self.catalog_path}")
        raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Catalog JSON must be a list of assessment records")
        items: list[Assessment] = []
        errors: list[str] = []
        for index, row in enumerate(raw):
            try:
                items.append(Assessment.model_validate(row))
            except ValidationError as exc:
                errors.append(f"record {index}: {exc}")
        if errors:
            raise ValueError("Invalid catalog data:\n" + "\n".join(errors[:10]))
        self._items = items
        logger.info("Loaded %s catalog assessments", len(items))
        return items

    def by_name(self, name: str) -> Assessment | None:
        normalized = normalize_name(name)
        for item in self.load():
            if normalize_name(item.name) == normalized:
                return item
        return None

    def find_mentions(self, text: str) -> list[Assessment]:
        lowered = text.lower()
        matches = []
        for item in self.load():
            name = item.name.lower()
            compact = name.replace(" - ", " ").replace("/", " ")
            if name in lowered or compact in lowered:
                matches.append(item)
        return matches


def normalize_name(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())
