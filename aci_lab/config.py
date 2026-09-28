from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


class ConfigurationError(RuntimeError):
    pass


class LabConfig:
    def __init__(self, root: Path):
        self.root = root
        self.config_dir = root / "config"
        self.inventory = self._yaml(self.config_dir / "inventory.yml")
        self.settings = self._yaml(self.config_dir / "lab_settings.yml")
        schema = json.loads((self.config_dir / "schema" / "chapter.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        self.chapters: dict[int, dict[str, Any]] = {}
        for path in sorted((self.config_dir / "chapters").glob("chapter_*.yml")):
            data = self._yaml(path)
            errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
            if errors:
                detail = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
                raise ConfigurationError(f"{path}: {detail}")
            self._apply_aliases(data)
            self.chapters[data["chapter"]] = data
        self._validate_inventory()

    @staticmethod
    def _yaml(path: Path) -> dict[str, Any]:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError(f"無法讀取 {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ConfigurationError(f"{path} 的最上層必須是 mapping")
        return value

    @staticmethod
    def _apply_aliases(chapter: dict[str, Any]) -> None:
        for obj in chapter.get("objects", []):
            aliases = obj.pop("attribute_aliases", {})
            for source, target in aliases.items():
                if source in obj["attributes"]:
                    obj["attributes"][target] = obj["attributes"].pop(source)

    def _validate_inventory(self) -> None:
        apics = self.inventory.get("apics", [])
        switches = self.inventory.get("switches", [])
        if len(apics) != 3 or len(switches) != 3:
            raise ConfigurationError("inventory 必須包含 3 台 APIC 與 3 台交換器")
        serials = [s["serial"] for s in switches]
        if len(serials) != len(set(serials)):
            raise ConfigurationError("交換器序號不可重複")

    def chapter_range(self, first: int, last: int) -> list[dict[str, Any]]:
        return [self.chapters[n] for n in range(first, last + 1) if n in self.chapters]

