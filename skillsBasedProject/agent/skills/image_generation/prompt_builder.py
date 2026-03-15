"""ImageGeneration Skill 运行时实现：分层提示词构建"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

STYLE_MAP = {
    "realistic": "写实风格，高清细节",
    "anime": "动漫风格，日式插画",
    "painting": "油画风格，艺术质感",
    "sketch": "素描风格，黑白线条",
    "3d": "3D渲染，立体感",
}


class ImageGenerationSkill:
    """图像生成 Skill：将场景转为图像 API 提示词"""

    def __init__(self, document_id: str, data_dir: str, config: dict):
        self.document_id = document_id
        self.data_dir = data_dir
        self.config = config

    def build_prompt(self, scene: Dict[str, Any], style: str = "realistic") -> str:
        """构建分层提示词：[Style] + [Subjects] + [Environment] + [Composition] + [Lighting] + [Atmosphere]"""
        parts = []

        parts.append(STYLE_MAP.get(style, STYLE_MAP["realistic"]))

        narrative = scene.get("narrative", "")[:300]
        if narrative:
            parts.append(narrative)

        key_elements = scene.get("key_elements", [])
        if key_elements:
            parts.append(f"场景包含：{', '.join(key_elements[:5])}")

        emotion_state = scene.get("emotion_state", {})
        if isinstance(emotion_state, dict) and emotion_state:
            emotions = ", ".join([f"{k}: {v}" for k, v in list(emotion_state.items())[:3]])
            parts.append(f"情感氛围：{emotions}")
        elif isinstance(emotion_state, str):
            parts.append(f"情感氛围：{emotion_state}")

        return "，".join(parts) if parts else "场景描述"
