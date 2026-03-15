"""StorylineControl Skill 运行时实现：分层约束与偏离度评估"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class StorylineControlSkill:
    """故事线控制 Skill：评估用户输入对故事线的影响"""

    def __init__(self, document_id: str, data_dir: str, config: dict):
        self.document_id = document_id
        self.data_dir = data_dir
        self.config = config

    def evaluate(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """评估用户输入的偏离度"""
        # 占位实现：返回默认允许继续
        # 完整实现需调用 LLM 或规则引擎
        return {
            "level": "on_track",
            "message": "选择合理，继续故事",
            "guidance": "",
            "allow_continue": True,
            "divergence": {"level": 0, "description": "", "key_changes": []},
        }
