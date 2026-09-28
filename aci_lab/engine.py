from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .apic import ApicClient


@dataclass
class Change:
    chapter: int
    action: str
    dn: str
    differences: dict[str, tuple[Any, Any]] = field(default_factory=dict)


class DeclarativeEngine:
    def __init__(self, client: ApicClient, dry_run: bool = False):
        self.client = client
        self.dry_run = dry_run

    @staticmethod
    def differences(actual: dict[str, Any], desired: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
        result = {}
        for key, expected in desired.items():
            found = actual.get(key)
            if str(found) != str(expected):
                result[key] = (found, expected)
        return result

    def inspect_chapter(self, chapter: dict[str, Any]) -> list[Change]:
        changes = []
        for obj in chapter["objects"]:
            state = self.client.get_object(obj["dn"])
            if not state.exists:
                changes.append(Change(chapter["chapter"], "CREATE", obj["dn"]))
                continue
            diff = self.differences(state.attributes, obj["attributes"])
            changes.append(Change(chapter["chapter"], "UPDATE" if diff else "MATCHED", obj["dn"], diff))
        return changes

    def apply_chapter(self, chapter: dict[str, Any]) -> list[Change]:
        changes = self.inspect_chapter(chapter)
        if self.dry_run:
            return changes
        by_dn = {obj["dn"]: obj for obj in chapter["objects"]}
        for change in changes:
            if change.action in {"CREATE", "UPDATE"}:
                obj = by_dn[change.dn]
                self.client.upsert(obj["class"], obj["dn"], obj["attributes"])
        verification = self.inspect_chapter(chapter)
        failed = [item for item in verification if item.action != "MATCHED"]
        if failed:
            dns = ", ".join(item.dn for item in failed)
            raise RuntimeError(f"章節 {chapter['chapter']} 寫入後驗證失敗: {dns}")
        return changes

    def cleanup_chapters(self, chapters: list[dict[str, Any]]) -> list[Change]:
        results = []
        for chapter in sorted(chapters, key=lambda c: c["chapter"], reverse=True):
            for obj in reversed(chapter["objects"]):
                state = self.client.get_object(obj["dn"])
                if state.exists:
                    results.append(Change(chapter["chapter"], "DELETE", obj["dn"]))
                    if not self.dry_run:
                        self.client.delete(obj["class"], obj["dn"])
        return results
