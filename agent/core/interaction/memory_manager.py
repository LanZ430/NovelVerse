"""记忆管理器模块，负责管理和检索交互历史中的重要信息

该模块负责维护长期记忆库，存储重要的事件、角色交互和关键情节，并根据当前场景检索相关记忆。
"""

from typing import Dict, Any, List, Optional
import logging
import re
import time

logger = logging.getLogger(__name__)

class MemoryManager:
    """记忆管理器，负责管理跨章节记忆和相关信息检索"""
    
    def __init__(self):
        """初始化记忆管理器"""
        self.memory_store = []  # 记忆存储
        
    def update_memory_store(self, scene: Dict[str, Any], character_name: str, current_chapter: int) -> None:
        """更新记忆库
        
        Args:
            scene: 场景信息，包含memory_update字段
            character_name: 角色名称
            current_chapter: 当前章节
        """
        memory_updates = scene.get('memory_update', [])
        if not memory_updates:
            return
            
        # 如果memory_update是字符串，将其转换为列表
        if isinstance(memory_updates, str):
            memory_updates = [memory_updates]
            
        # 为每条记忆添加元数据并存储
        for memory in memory_updates:
            # 根据当前场景生成重要性评分
            # 简单规则：记忆重要性与章节进度成正比
            progress = scene.get('progress_info', {}).get('progress', 50)
            importance = min(100, max(1, progress)) / 20  # 转换为1-5范围
            
            memory_item = {
                'content': memory,
                'chapter': current_chapter,
                'character': character_name,
                'timestamp': self._get_current_timestamp(),
                'importance': importance
            }
            
            # 防止重复记忆
            if not any(m['content'] == memory for m in self.memory_store):
                self.memory_store.append(memory_item)
    
    def get_cross_chapter_memory(self, max_memories: int = 20) -> List[Dict[str, Any]]:
        """获取跨章节记忆
        
        Args:
            max_memories: 最大记忆数量
            
        Returns:
            List[Dict[str, Any]]: 跨章节记忆列表
        """
        # 如果记忆超过指定数量，只返回最重要的记忆
        if len(self.memory_store) > max_memories:
            return sorted(self.memory_store, key=lambda x: x.get('importance', 0), reverse=True)[:max_memories]
        return self.memory_store
    
    def get_related_memories(self, query: str, max_memories: int = 10) -> List[Dict[str, Any]]:
        """获取与查询相关的记忆
        
        Args:
            query: 用户输入或查询字符串
            max_memories: 最大返回记忆数量
            
        Returns:
            List[Dict[str, Any]]: 相关记忆列表
        """
        if not query or not self.memory_store:
            return []
            
        # 提取查询关键词
        keywords = [word for word in re.sub(r'[^\w\s]', '', query.lower()).split() if len(word) > 1]
        if not keywords:
            return []
            
        # 对每条记忆评分
        scored_memories = []
        for memory in self.memory_store:
            content = memory.get('content', '').lower()
            score = 0
            
            # 按关键词匹配度评分
            for keyword in keywords:
                if keyword in content:
                    score += 1
                    
            # 考虑记忆的重要性
            score *= memory.get('importance', 1)
            
            if score > 0:
                scored_memories.append((memory, score))
                
        # 按评分排序并取前N条
        if not scored_memories:
            # 如果没有相关记忆，返回最重要的几条记忆
            important_memories = sorted(self.memory_store, key=lambda x: x.get('importance', 0), reverse=True)
            return important_memories[:max_memories]
            
        sorted_memories = [m[0] for m in sorted(scored_memories, key=lambda x: x[1], reverse=True)]
        return sorted_memories[:max_memories]
    
    def generate_chapter_summary(self, scenes: List[Dict[str, Any]], current_chapter: int, character_name: str, client, llm_model) -> None:
        """生成章节摘要并添加到记忆库
        
        Args:
            scenes: 章节中的场景列表
            current_chapter: 当前章节
            character_name: 角色名称
            client: LLM客户端
            llm_model: 使用的模型
        """
        # 提取所有场景的叙述部分和关键元素
        narratives = [scene.get('narrative', '') for scene in scenes if scene.get('narrative')]
        key_elements = [element for scene in scenes for element in scene.get('key_elements', [])]
        
        # 构建章节内容
        chapter_content = "\n\n".join(narratives)
        
        # 如果内容太少，不生成摘要
        if len(chapter_content) < 100:
            return
            
        # 构建摘要提示
        prompt = f"""你是一个小说摘要助手。请为以下章节内容生成一个简洁的摘要。

### 基本信息
- 角色：{character_name}
- 章节：第{current_chapter}章

### 章节内容
{chapter_content}

### 关键元素
{', '.join(key_elements[:10])}

请生成两部分内容：
1. 章节摘要：200字左右的摘要，概括主要情节发展
2. 关键线索：3-5个本章节出现的重要线索或关键信息点

格式应为JSON：
{{
    "summary": "章节摘要内容...",
    "key_clues": ["线索1", "线索2", "线索3"]
}}"""
        
        try:
            # 调用LLM生成摘要
            import json
            response = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=800
            )
            
            content = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 处理可能的markdown代码块
                if content.startswith('```json') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                elif content.startswith('```') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                    
                summary_data = json.loads(content)
                
                # 添加章节摘要到记忆库
                summary = summary_data.get('summary', '')
                if summary:
                    self.memory_store.append({
                        'content': f"第{current_chapter}章摘要：{summary}",
                        'chapter': current_chapter,
                        'character': character_name,
                        'timestamp': self._get_current_timestamp(),
                        'importance': 5,  # 章节摘要很重要
                        'type': 'chapter_summary'
                    })
                
                # 添加关键线索到记忆库
                key_clues = summary_data.get('key_clues', [])
                for i, clue in enumerate(key_clues):
                    self.memory_store.append({
                        'content': f"第{current_chapter}章线索：{clue}",
                        'chapter': current_chapter,
                        'character': character_name,
                        'timestamp': self._get_current_timestamp(),
                        'importance': 4.5 - (i * 0.2),  # 线索按顺序略微降低重要性
                        'type': 'key_clue'
                    })
                    
                logger.info(f"已生成第{current_chapter}章摘要和{len(key_clues)}个关键线索")
                
            except json.JSONDecodeError:
                logger.warning("LLM返回的章节摘要不是有效的JSON格式")
                
        except Exception as e:
            logger.error(f"生成章节摘要失败: {str(e)}")
    
    def load_memories(self, memory_data: List[Dict[str, Any]]) -> None:
        """加载记忆数据
        
        Args:
            memory_data: 记忆数据列表
        """
        self.memory_store = memory_data
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳
        
        Returns:
            str: 时间戳字符串
        """
        import datetime
        return datetime.datetime.now().isoformat() 