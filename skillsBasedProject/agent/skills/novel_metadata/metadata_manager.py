"""NovelMetadata Skill 运行时实现：提供角色、情节、设定等上下文"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class NovelMetadataSkill:
    """元数据 Skill：加载并提供 Book Skill 包中的元数据"""

    def __init__(self, document_id: str, data_dir: str, config: dict):
        self.document_id = document_id
        self.data_dir = Path(data_dir)
        self.config = config
        self._characters: Dict[str, Any] = {}
        self._plots: List[Dict] = []
        self._settings: Dict[str, Any] = {}
        self._world_metadata: Dict[str, Any] = {}
        self._load_book_skill()

    def _load_book_skill(self) -> None:
        """加载 Book Skill 包"""
        base = self.data_dir / "books" / self.document_id
        if not base.exists():
            base = self.data_dir / "characters" / self.document_id
            if base.exists():
                char_file = self.data_dir / "characters" / self.document_id / "characters.json"
                if char_file.exists():
                    with open(char_file, "r", encoding="utf-8") as f:
                        self._characters = json.load(f)

            plots_dir = self.data_dir / "plots" / self.document_id
            if plots_dir.exists():
                plots_file = plots_dir / "plots.json"
                if plots_file.exists():
                    with open(plots_file, "r", encoding="utf-8") as f:
                        self._plots = json.load(f)

            settings_dir = self.data_dir / "settings" / self.document_id
            if settings_dir.exists():
                settings_file = settings_dir / "settings.json"
                if settings_file.exists():
                    with open(settings_file, "r", encoding="utf-8") as f:
                        self._settings = json.load(f)
            return

        for path in [base / "characters.json", base / "characters"]:
            if path.exists():
                if path.is_file():
                    with open(path, "r", encoding="utf-8") as f:
                        self._characters = json.load(f)
                break

        plots_file = base / "plots.json"
        if plots_file.exists():
            with open(plots_file, "r", encoding="utf-8") as f:
                self._plots = json.load(f)

        settings_file = base / "settings.json"
        if settings_file.exists():
            with open(settings_file, "r", encoding="utf-8") as f:
                self._settings = json.load(f)

        world_file = base / "world_metadata.json"
        if world_file.exists():
            with open(world_file, "r", encoding="utf-8") as f:
                self._world_metadata = json.load(f)

    def get_context(self, character_name: str, chapter: int) -> Dict[str, Any]:
        """为场景生成提供完整上下文"""
        character_info = None
        if isinstance(self._characters, dict):
            character_info = self._characters.get(character_name)
            if character_info is None:
                for k, v in self._characters.items():
                    if isinstance(v, dict) and v.get("name") == character_name:
                        character_info = v
                        break
        elif isinstance(self._characters, list):
            for c in self._characters:
                if c.get("name") == character_name:
                    character_info = c
                    break

        chapter_summary = None
        chapter_events = []
        if isinstance(self._plots, list):
            for p in self._plots:
                if p.get("chapter") == chapter or str(p.get("chapter")) == str(chapter):
                    chapter_summary = p.get("summary") or p.get("description")
                    chapter_events = p.get("events", [])
                    if not chapter_events and p.get("description"):
                        chapter_events = [{"description": p["description"]}]
                    break

        return {
            "character_info": character_info,
            "chapter_summary": chapter_summary,
            "chapter_events": chapter_events,
            "world_settings": self._settings,
            "world_metadata": self._world_metadata,
            "plot_anchors": self._plots,
            "summary": f"{character_name} 第{chapter}章",
        }

    def validate_scene(self, scene: Dict[str, Any], character_name: str, chapter: int) -> Dict[str, Any]:
        """验证场景是否符合元数据约束（占位实现）"""
        return {"valid": True, "issues": []}
