"""VoiceGeneration Skill 运行时实现：对话提取与 TTS 调用占位"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class VoiceGenerationSkill:
    """语音生成 Skill：从场景提取对话并生成语音"""

    def __init__(self, document_id: str, data_dir: str, config: dict):
        self.document_id = document_id
        self.data_dir = data_dir
        self.config = config

    def generate(self, scene: Dict[str, Any]) -> Dict[str, Any]:
        """为场景生成语音（占位实现）"""
        narrative = scene.get("narrative", "")
        dialogues = self._extract_dialogues(narrative)

        if not dialogues:
            return {"status": "warning", "message": "未检测到对话", "dialogues": []}

        # 占位：实际需调用 TTS API
        return {
            "status": "skipped",
            "message": "TTS 未配置或未实现",
            "dialogues": [{"speaker": d["speaker"], "content": d["content"]} for d in dialogues],
        }

    def _extract_dialogues(self, text: str) -> List[Dict[str, str]]:
        """从文本提取对话（规则实现）"""
        dialogues = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            for sep in ["：", ": "]:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                        dialogues.append({"speaker": parts[0].strip(), "content": parts[1].strip()})
                    break
        return dialogues
