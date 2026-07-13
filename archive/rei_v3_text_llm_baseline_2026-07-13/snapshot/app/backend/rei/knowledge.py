from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any

from .models import CharacterDefinition, KnowledgeRef, MindDefinition


class KnowledgeIndex:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    @cached_property
    def refs(self) -> list[KnowledgeRef]:
        return [KnowledgeRef.model_validate(item) for item in self.raw["knowledge_refs"]]

    @cached_property
    def minds(self) -> list[MindDefinition]:
        return [MindDefinition.model_validate(item) for item in self.raw["minds"]]

    @cached_property
    def characters(self) -> list[CharacterDefinition]:
        return [CharacterDefinition.model_validate(item) for item in self.raw["characters"]]

    @cached_property
    def mind_map(self) -> dict[str, MindDefinition]:
        return {mind.id: mind for mind in self.minds}

    @cached_property
    def character_map(self) -> dict[str, CharacterDefinition]:
        return {character.id: character for character in self.characters}

    def ref(self, ref_id: str) -> KnowledgeRef:
        for ref in self.refs:
            if ref.id == ref_id:
                return ref
        return KnowledgeRef(id=ref_id, kind="IZ", label=ref_id)

    def shared_refs(self) -> list[KnowledgeRef]:
        keep = {
            "OD-OSN",
            "OD-R",
            "OD-E",
            "OD-I",
            "OD-13",
            "EK-Sodelovanje-med-razumi",
            "EK-O-nesprejemanju",
            "PD-GEO",
            "PD-ANT",
            "PD-PSI",
            "IZ-APP",
        }
        return [ref for ref in self.refs if ref.id in keep]

