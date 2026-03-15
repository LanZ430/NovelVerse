"""Skill 编排器：协调各 Skill 的加载、依赖解析与调用"""

import logging
from typing import Dict, Any, List

from .registry import SKILL_REGISTRY, SkillDefinition

logger = logging.getLogger(__name__)


class SkillOrchestrator:
    """协调各 Skill 的加载、依赖解析与调用"""

    def __init__(self, document_id: str, data_dir: str = "./data", config: Dict[str, Any] = None):
        self.document_id = document_id
        self.data_dir = data_dir
        self.config = config or {}
        self.skills: Dict[str, Any] = {}
        self._load_skills()

    def _instantiate_skill(self, definition: SkillDefinition) -> Any:
        """实例化 Skill 模块"""
        try:
            module = __import__(definition.module_path, fromlist=[""])
            if hasattr(module, "create_skill"):
                return module.create_skill(
                    document_id=self.document_id,
                    data_dir=self.data_dir,
                    config=self.config,
                )
            if hasattr(module, "Skill"):
                return module.Skill(
                    document_id=self.document_id,
                    data_dir=self.data_dir,
                    config=self.config,
                )
            logger.warning(f"Skill {definition.name} 无标准工厂或类")
            return None
        except Exception as e:
            logger.exception(f"加载 Skill {definition.name} 失败: {e}")
            return None

    def _load_skills(self) -> None:
        """按依赖顺序加载 Skill"""
        loaded: set = set()

        def load_skill(name: str) -> None:
            if name in loaded:
                return
            definition = SKILL_REGISTRY.get(name)
            if not definition:
                logger.warning(f"未找到 Skill 定义: {name}")
                return
            for req in definition.requires:
                load_skill(req)
            instance = self._instantiate_skill(definition)
            if instance:
                self.skills[name] = instance
                loaded.add(name)
                logger.info(f"已加载 Skill: {name}")

        for skill_name in SKILL_REGISTRY:
            load_skill(skill_name)

    def get_context_for_scene(self, character_name: str, chapter: int) -> Dict[str, Any]:
        """聚合各 Skill 输出，生成场景上下文"""
        metadata = {}
        if "novel-metadata" in self.skills:
            skill = self.skills["novel-metadata"]
            if hasattr(skill, "get_context"):
                metadata = skill.get_context(character_name, chapter) or {}

        memories = []
        if "memory-architecture" in self.skills:
            skill = self.skills["memory-architecture"]
            if hasattr(skill, "retrieve"):
                query = metadata.get("summary", "") or f"{character_name} 第{chapter}章"
                memories = skill.retrieve(query, max_results=10) or []

        return {
            **metadata,
            "cross_chapter_memory": memories,
        }

    def evaluate_input(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """调用 StorylineControl 评估输入"""
        if "storyline-control" not in self.skills:
            return {"level": "unknown", "message": "StorylineControl 未加载", "allow_continue": True}
        skill = self.skills["storyline-control"]
        if hasattr(skill, "evaluate"):
            return skill.evaluate(user_input, context)
        return {"level": "unknown", "allow_continue": True}

    def generate_image_prompt(self, scene: Dict[str, Any], style: str = "realistic") -> str:
        """调用 ImageGeneration 生成提示词"""
        if "image-generation" not in self.skills:
            narrative = scene.get("narrative", "")[:300]
            return narrative or "场景描述"
        skill = self.skills["image-generation"]
        if hasattr(skill, "build_prompt"):
            return skill.build_prompt(scene, style)
        return scene.get("narrative", "")[:300]

    def generate_voice_for_scene(self, scene: Dict[str, Any]) -> Dict[str, Any]:
        """调用 VoiceGeneration 生成语音"""
        if "voice-generation" not in self.skills:
            return {"status": "skipped", "message": "VoiceGeneration 未加载", "dialogues": []}
        skill = self.skills["voice-generation"]
        if hasattr(skill, "generate"):
            return skill.generate(scene)
        return {"status": "skipped", "dialogues": []}

    def store_memory(self, memory_type: str, content: Dict[str, Any], importance: float = 0.5) -> None:
        """存储记忆"""
        if "memory-architecture" not in self.skills:
            return
        skill = self.skills["memory-architecture"]
        if hasattr(skill, "store_memory"):
            skill.store_memory(memory_type, content, importance)
