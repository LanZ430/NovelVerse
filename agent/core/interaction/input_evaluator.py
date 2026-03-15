"""输入评估器模块，负责评估用户输入及其对故事发展的影响

该模块用于分析用户的选择，评估其对故事情节的影响、偏离程度和情感变化。
"""

from typing import Dict, Any, List, Optional
import logging
import json
import re
import time

logger = logging.getLogger(__name__)

class InputEvaluator:
    """输入评估器，负责评估用户输入对故事发展的影响"""
    
    def __init__(self, client, llm_model, document_language='chinese'):
        """初始化输入评估器
        
        Args:
            client: LLM客户端
            llm_model: 使用的语言模型
            document_language: 文档语言，默认'chinese'
        """
        self.client = client
        self.llm_model = llm_model
        self.document_language = document_language
    
    def evaluate_user_input(self, user_input: str, last_scene: Dict[str, Any], 
                           character_name: str, current_chapter: int,
                           character_info: Dict[str, Any] = None,
                           chapter_summary: Dict[str, Any] = None,
                           chapter_events: List[Dict[str, Any]] = None,
                           related_memories: List[Dict[str, Any]] = None,
                           current_progress: int = 0,
                           recent_divergences: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """评估用户输入
        
        Args:
            user_input: 用户输入
            last_scene: 上一个场景
            character_name: 角色名称
            current_chapter: 当前章节
            character_info: 角色信息
            chapter_summary: 章节摘要
            chapter_events: 章节事件
            related_memories: 相关记忆
            current_progress: 当前进度
            recent_divergences: 最近的偏离
            
        Returns:
            Dict[str, Any]: 评估结果
        """
        # 获取交互ID
        interaction_id = last_scene.get('interaction_id', f"ch{current_chapter}_{int(time.time())}")
        
        # 构建评估模板
        evaluation_template = {
            "should_proceed_chapter": False,
            "divergence": {
                "level": 0,  # 0-5的偏离度
                "description": "",
                "key_changes": []
            },
            "character_impact": {
                "consistent": True,
                "development": []
            },
            "next_steps": [],
            "needs_correction": False,
            "progress": current_progress
        }
        
        # 构建提示
        prompt = self._build_evaluation_prompt(
            character_name, current_chapter, interaction_id,
            character_info, chapter_summary, chapter_events, related_memories,
            last_scene, user_input, current_progress, recent_divergences,
            evaluation_template
        )
        
        # 调用LLM进行评估
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=1200
            )
            
            content = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 处理可能的markdown代码块
                if content.startswith('```json') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                elif content.startswith('```') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                    
                evaluation = json.loads(content)
                return evaluation
            except json.JSONDecodeError:
                logger.warning("LLM返回的内容不是有效的JSON格式")
                
                # 尝试查找JSON内容
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, content)
                
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        logger.error("无法解析提取的JSON内容")
                
                # 返回一个基本的评估
                return {
                    "should_proceed_chapter": False,
                    "divergence": {"level": 0, "description": "无法评估", "key_changes": []},
                    "character_impact": {"consistent": True, "development": []},
                    "next_steps": ["继续当前章节"],
                    "needs_correction": False,
                    "progress": current_progress
                }
                
        except Exception as e:
            logger.exception(f"评估用户输入失败: {str(e)}")
            raise
    
    def _build_evaluation_prompt(self, character_name: str, current_chapter: int, interaction_id: str,
                              character_info: Dict[str, Any], chapter_summary: Dict[str, Any],
                              chapter_events: List[Dict[str, Any]], related_memories: List[Dict[str, Any]],
                              last_scene: Dict[str, Any], user_input: str, 
                              current_progress: int, recent_divergences: List[Dict[str, Any]],
                              evaluation_template: Dict[str, Any]) -> str:
        """构建评估提示
        
        Returns:
            str: 提示词
        """
        if self.document_language == 'english':
            return f"""Evaluate the user's choice in an interactive story and analyze its impact.

### Basic Information
- Character: {character_name}
- Chapter: {current_chapter}
- Interaction ID: {interaction_id}

### Character Information
{json.dumps(character_info, ensure_ascii=False, indent=2) if character_info else "No character information"}

### Current Chapter Summary
{json.dumps(chapter_summary, ensure_ascii=False, indent=2) if chapter_summary else "No chapter summary"}

### Current Events
{json.dumps(chapter_events, ensure_ascii=False, indent=2) if chapter_events else "No event information"}

### Related Memories and Clues
{json.dumps(related_memories, ensure_ascii=False, indent=2) if related_memories else "No related memories and clues"}

### Previous Scene
{json.dumps(last_scene, ensure_ascii=False, indent=2)}

### User Choice
{user_input}

### Current Interaction Status
- Progress: {current_progress}%
- Existing Divergences: {json.dumps(recent_divergences, ensure_ascii=False)}

Please evaluate:

1. **Story Progression**: Does it advance the story? Should we move to the next chapter?
2. **Plot Divergence**: The degree of divergence from the original story (0-5), and note key changes.
3. **Character Consistency**: Does the choice align with {character_name}'s personality? Does it foster character development?
4. **Future Impact**: Predict 2-3 possible subsequent developments.
5. **Need for Correction**: If the choice deviates too much, should it be guided back to the main storyline?
6. **Progress Assessment**: What percentage of the story progress (0-100%) does this choice advance to?

The evaluation result must be in strictly parsable JSON format:
{json.dumps(evaluation_template, ensure_ascii=False, indent=2)}"""
        else:
            return f"""评估用户在小说交互中做出的选择，分析其对故事的影响。

### 基本信息
- 角色: {character_name}
- 章节: {current_chapter}
- 交互ID: {interaction_id}

### 角色信息
{json.dumps(character_info, ensure_ascii=False, indent=2) if character_info else "无角色信息"}

### 当前章节摘要
{json.dumps(chapter_summary, ensure_ascii=False, indent=2) if chapter_summary else "无章节摘要"}

### 当前事件
{json.dumps(chapter_events, ensure_ascii=False, indent=2) if chapter_events else "无事件信息"}

### 相关记忆和线索
{json.dumps(related_memories, ensure_ascii=False, indent=2) if related_memories else "无相关记忆和线索"}

### 上一个场景
{json.dumps(last_scene, ensure_ascii=False, indent=2)}

### 用户选择
{user_input}

### 当前交互状态
- 进度: {current_progress}%
- 已有偏离: {json.dumps(recent_divergences, ensure_ascii=False)}

请评估:

1. **故事进展**: 是否推动了故事发展？是否应进入下一章？
2. **情节偏离度**: 这个选择与原故事的偏离程度(0-5)，并说明关键变化。
3. **角色一致性**: 选择是否符合{character_name}的性格？是否促进角色发展？
4. **后续影响**: 预测2-3个可能的后续发展。
5. **是否需要修正**: 如果选择太过偏离，是否需要引导回主线？
6. **进度评估**: 这个选择将故事进度推进到了多少百分比(0-100)？

评估结果必须是严格可解析的JSON格式:
{json.dumps(evaluation_template, ensure_ascii=False, indent=2)}""" 