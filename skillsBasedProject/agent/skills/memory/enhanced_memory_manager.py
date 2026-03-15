"""MemoryArchitecture Skill 运行时实现：分层记忆与检索"""

import logging
import time
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class MemoryArchitectureSkill:
    """记忆架构 Skill：情景/语义/工作/长期记忆"""

    def __init__(self, document_id: str, data_dir: str, config: dict):
        self.document_id = document_id
        self.data_dir = data_dir
        self.config = config
        self._memory_store: List[Dict[str, Any]] = []

    def store_memory(self, memory_type: str, content: Dict[str, Any], importance: float = 0.5) -> None:
        """存储记忆"""
        self._memory_store.append({
            "type": memory_type,
            "content": content,
            "importance": importance,
            "timestamp": time.time(),
        })

    def retrieve(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """检索相关记忆（简化实现：关键词匹配）"""
        if not query or not self._memory_store:
            return []

        query_lower = query.lower()
        scored = []
        for m in self._memory_store:
            text = str(m.get("content", ""))
            if query_lower in text.lower():
                scored.append({**m, "score": m.get("importance", 0.5)})

        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        return scored[:max_results]
