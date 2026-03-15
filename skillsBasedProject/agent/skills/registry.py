"""Skill 注册表：定义各 Skill 的元数据与依赖关系"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class SkillDefinition:
    """Skill 定义"""
    name: str
    description: str
    requires: List[str]  # 依赖的 Skill 名称
    provides: List[str]  # 提供给其他组件的输出
    module_path: str     # 运行时模块路径


SKILL_REGISTRY: Dict[str, SkillDefinition] = {
    "novel-metadata": SkillDefinition(
        name="novel-metadata",
        description="Novel metadata management",
        requires=[],
        provides=["character_context", "plot_anchors", "world_settings"],
        module_path="agent.skills.novel_metadata",
    ),
    "storyline-control": SkillDefinition(
        name="storyline-control",
        description="Storyline divergence control",
        requires=["novel-metadata"],
        provides=["divergence_evaluation", "guidance"],
        module_path="agent.skills.storyline_control",
    ),
    "image-generation": SkillDefinition(
        name="image-generation",
        description="Scene-to-image prompt optimization",
        requires=["novel-metadata"],
        provides=["image_prompt", "style_recommendation"],
        module_path="agent.skills.image_generation",
    ),
    "memory-architecture": SkillDefinition(
        name="memory-architecture",
        description="Layered memory management",
        requires=[],
        provides=["relevant_memories", "memory_update"],
        module_path="agent.skills.memory",
    ),
    "voice-generation": SkillDefinition(
        name="voice-generation",
        description="Dialogue to speech conversion",
        requires=["novel-metadata"],
        provides=["audio_paths", "dialogue_audio"],
        module_path="agent.skills.voice",
    ),
}
