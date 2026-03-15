"""场景生成器模块，负责生成故事场景

该模块包含与场景生成相关的功能，包括初始场景、普通场景和偏离结局场景的生成。
"""

from typing import Dict, Any, List, Optional
import logging
import json
import re
import time

logger = logging.getLogger(__name__)

class SceneGenerator:
    """场景生成器，负责生成各种故事场景"""
    
    def __init__(self, client, llm_model, document_language='chinese'):
        """初始化场景生成器
        
        Args:
            client: LLM客户端
            llm_model: 使用的语言模型
            document_language: 文档语言，默认'chinese'
        """
        self.client = client
        self.llm_model = llm_model
        self.document_language = document_language
    
    def generate_scene(self, character_name: str, current_chapter: int, 
                      character_info: Dict[str, Any] = None, 
                      chapter_summary: Dict[str, Any] = None,
                      chapter_events: List[Dict[str, Any]] = None,
                      cross_chapter_memory: List[Dict[str, Any]] = None,
                      user_input: str = "", 
                      evaluation: Dict[str, Any] = None,
                      current_progress: int = 0,
                      recent_choices: List[Dict[str, Any]] = None,
                      recent_divergences: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """生成场景
        
        Args:
            character_name: 角色名称
            current_chapter: 当前章节
            character_info: 角色信息
            chapter_summary: 章节摘要
            chapter_events: 章节事件
            cross_chapter_memory: 跨章节记忆
            user_input: 用户输入
            evaluation: 评估结果
            current_progress: 当前进度
            recent_choices: 最近选择
            recent_divergences: 最近偏离
            
        Returns:
            Dict[str, Any]: 场景信息
        """
        # 生成交互ID
        interaction_id = f"ch{current_chapter}_{int(time.time())}"
        
        # 构建提示
        # 视角和语言指示
        perspective_instruction = self._get_perspective_instruction(character_name)
        
        # 基于是否有用户输入构建不同的提示
        if user_input and evaluation:
            prompt = self._build_continue_scene_prompt(
                character_name, current_chapter, interaction_id,
                character_info, chapter_summary, chapter_events, cross_chapter_memory,
                user_input, evaluation, current_progress, recent_choices, recent_divergences,
                perspective_instruction
            )
        else:
            prompt = self._build_initial_scene_prompt(
                character_name, current_chapter, interaction_id,
                character_info, chapter_summary, chapter_events, cross_chapter_memory,
                perspective_instruction
            )
        
        # 调用LLM生成场景
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.7,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 处理可能的markdown代码块
                if content.startswith('```json') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                elif content.startswith('```') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                    
                scene = json.loads(content)
                
                # 添加交互ID
                scene['interaction_id'] = interaction_id
                
                # 验证视角是否正确
                narrative = scene.get('narrative', '')
                if not self._validate_first_person_perspective(narrative, character_name):
                    logger.warning("生成的内容不是第一人称视角，进行修正")
                    scene['narrative'] = self._fix_perspective(narrative, character_name)
                
                # 处理情感状态
                if isinstance(scene.get('emotion_state'), dict):
                    emotion_state = scene['emotion_state']
                    if character_name in emotion_state:
                        emotion_state['我'] = emotion_state.pop(character_name)
                
                return scene
            except json.JSONDecodeError:
                logger.warning("LLM返回的内容不是有效的JSON格式")
                
                # 尝试查找JSON内容
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, content)
                
                if match:
                    try:
                        scene = json.loads(match.group(0))
                        scene['interaction_id'] = interaction_id
                        return scene
                    except json.JSONDecodeError:
                        logger.error("无法解析提取的JSON内容")
                
                # 返回一个基本的场景
                return {
                    "narrative": f"我（{character_name}）站在这里，思考着接下来该怎么做。",
                    "interaction_point": "我需要做出一个决定...",
                    "context_hint": "考虑当前的情况，我可以怎么行动？",
                    "key_elements": ["我", "当前环境", "面临的选择"],
                    "emotion_state": {"我": "思考中"},
                    "interaction_id": interaction_id,
                    "progress_info": {
                        "current_scene": "继续故事",
                        "progress": current_progress,
                        "next_key_events": ["故事发展"]
                    }
                }
                
        except Exception as e:
            logger.exception(f"生成场景失败: {str(e)}")
            raise
    
    def generate_deviation_scene(self, character_name: str, current_chapter: int, 
                                user_input: str, last_scene: Dict[str, Any],
                                character_info: Dict[str, Any] = None,
                                chapter_summary: Dict[str, Any] = None,
                                last_divergence: Dict[str, Any] = None,
                                cross_chapter_memory: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """生成偏离结局场景
        
        Args:
            character_name: 角色名称
            current_chapter: 当前章节
            user_input: 用户输入
            last_scene: 上一个场景
            character_info: 角色信息
            chapter_summary: 章节摘要
            last_divergence: 最后一次偏离信息
            cross_chapter_memory: 跨章节记忆
            
        Returns:
            Dict[str, Any]: 偏离结局场景
        """
        logger.info(f"用户选择继续偏离主线的故事: {user_input}")
        
        # 生成交互ID
        interaction_id = f"ch{current_chapter}_dev_{int(time.time())}"
        
        # 构建特殊的偏离结局提示
        prompt = f"""你是一个沉浸式小说交互系统。用户已明确选择继续一个偏离主线的故事方向。基于用户的选择，生成一个偏离主线但符合逻辑的结局场景。

### 基本信息
- 角色：{character_name}
- 当前章节：{current_chapter}
- 交互ID：{interaction_id}
- 注意：用户已明确选择继续偏离主线故事，请生成一个合理的替代结局

### 角色信息
{json.dumps(character_info, ensure_ascii=False, indent=2) if character_info else "无角色信息"}

### 章节信息
{json.dumps(chapter_summary, ensure_ascii=False, indent=2) if chapter_summary else "无章节信息"}

### 偏离信息
{json.dumps(last_divergence, ensure_ascii=False, indent=2) if last_divergence else "无具体偏离信息"}

### 跨章节记忆
{json.dumps(cross_chapter_memory, ensure_ascii=False, indent=2) if cross_chapter_memory else "无跨章节记忆"}

### 上一个场景
{json.dumps(last_scene, ensure_ascii=False, indent=2)}

### 用户选择
{user_input}

### 偏离结局生成指南
1. 必须严格从{character_name}的第一人称视角描述场景和内心感受
2. 创建一个有情感和细节的结局场景（300-400字），具有一定的完整性和结局感
3. 基于用户的选择，生成一个虽然偏离原故事主线，但在逻辑上合理自洽的结局
4. 确保情绪状态和场景描述与角色身份一致
5. 必须描述用户扮演的对话者的反应、表情和态度变化
6. 环境应该随着情节的发展而变化，描述光线、气氛、声音等细节的变化
7. 标记这是一个偏离主线的结局，让用户知道这条叙事支线已经结束
8. 提供一个情感上有共鸣的收尾，可以是开放式的但要有一定的完结感

请以JSON格式返回，包含以下字段：
- narrative: 从{character_name}第一人称视角的结局场景描述（必须使用"我"，不能用"{character_name}"）
- deviated_ending: true（固定值，表示这是一个偏离主线的结局）
- ending_type: 结局类型的简短描述（如"悲剧"、"开放式"、"圆满"等）
- key_elements: 当前结局场景中的3-5个关键元素（简短列表）
- emotion_state: 结局场景中主要角色的情感状态，包括交互对象的情绪
- memory_update: 应该被记住的关键事件或信息（1-3条简短描述）
- deviation_summary: 简短描述偏离主线的关键决策点和结果
- progress_info: {{
    "current_scene": "结局场景简短描述",
    "progress": 100,
    "is_ending": true
}}"""
        
        # 调用LLM生成偏离结局场景
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.7,
                max_tokens=1800
            )
            
            content = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 处理可能的markdown代码块
                if content.startswith('```json') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                elif content.startswith('```') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                    
                scene = json.loads(content)
                
                # 添加交互ID和标记这是偏离结局
                scene['interaction_id'] = interaction_id
                scene['deviated_ending'] = True
                
                # 验证视角是否正确
                narrative = scene.get('narrative', '')
                if not self._validate_first_person_perspective(narrative, character_name):
                    logger.warning("生成的内容不是第一人称视角，进行修正")
                    scene['narrative'] = self._fix_perspective(narrative, character_name)
                
                # 处理情感状态
                if isinstance(scene.get('emotion_state'), dict):
                    emotion_state = scene['emotion_state']
                    if character_name in emotion_state:
                        emotion_state['我'] = emotion_state.pop(character_name)
                
                # 设置进度为100%
                if 'progress_info' not in scene:
                    scene['progress_info'] = {
                        "current_scene": "偏离主线结局",
                        "progress": 100,
                        "is_ending": True
                    }
                
                return scene
                
            except json.JSONDecodeError:
                logger.warning("LLM返回的内容不是有效的JSON格式")
                
                # 尝试查找JSON内容
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, content)
                
                if match:
                    try:
                        scene = json.loads(match.group(0))
                        scene['interaction_id'] = interaction_id
                        scene['deviated_ending'] = True
                        return scene
                    except json.JSONDecodeError:
                        logger.error("无法解析提取的JSON内容")
                
                # 返回一个基本的结局场景
                fallback_scene = {
                    "narrative": f"我（{character_name}）的选择让事情走向了一个不同的方向。[此处是系统生成的偏离主线结局]",
                    "deviated_ending": True,
                    "ending_type": "偏离结局",
                    "key_elements": ["偏离", "结局", "选择"],
                    "emotion_state": {"我": "复杂"},
                    "interaction_id": interaction_id,
                    "progress_info": {
                        "current_scene": "偏离主线结局",
                        "progress": 100,
                        "is_ending": True
                    }
                }
                
                return fallback_scene
                
        except Exception as e:
            logger.exception(f"生成偏离结局场景失败: {str(e)}")
            raise
    
    def _get_perspective_instruction(self, character_name: str) -> str:
        """获取视角指令
        
        Args:
            character_name: 角色名称
            
        Returns:
            str: 视角指令
        """
        if self.document_language == 'english':
            return f"""IMPORTANT: The player has chosen to play as the character "{character_name}". All content must be generated from the first-person perspective of "{character_name}".
Use "I" instead of "you" to refer to {character_name}, and refer to other characters as "you" or by their names.
The description should reflect what {character_name} sees, hears, and feels, expressing {character_name}'s thoughts and feelings.

You MUST generate ALL content in English only. Match your writing style to the original English text.
Use appropriate English vocabulary, idioms, and expressions. DO NOT use any Chinese in your response."""
        else:
            return f"""重要：玩家已选择扮演角色"{character_name}"，所有内容必须从"{character_name}"的第一人称视角生成。
使用"我"而不是"你"来指代{character_name}，将其他角色作为"你"或使用他们的名字来指代。
描述应反映{character_name}看到、听到、感受到的一切，体现{character_name}的思想和感受。

场景描述必须同时包含交互对象（用户角色）的反应和情绪变化，以及环境随情节发展的变化。
交互对象不仅是倾听者，也是具有性格特征和反应的角色，要描述其行为、表情和态度随情节发展而变化。
环境细节（如光线、气氛、周围物体）应该根据剧情的发展相应变化，增强沉浸感。"""
    
    def _build_continue_scene_prompt(self, character_name: str, current_chapter: int, interaction_id: str,
                                 character_info: Dict[str, Any], chapter_summary: Dict[str, Any],
                                 chapter_events: List[Dict[str, Any]], cross_chapter_memory: List[Dict[str, Any]],
                                 user_input: str, evaluation: Dict[str, Any], 
                                 current_progress: int, recent_choices: List[Dict[str, Any]], 
                                 recent_divergences: List[Dict[str, Any]], perspective_instruction: str) -> str:
        """构建继续场景提示
        
        Returns:
            str: 提示词
        """
        return f"""你是一个沉浸式小说交互系统。基于用户的选择，生成新的场景。严格遵循以下要求：

{perspective_instruction}

### 基本信息
- 角色：{character_name}
- 当前章节：{current_chapter}
- 交互ID：{interaction_id}

### 角色信息
{json.dumps(character_info, ensure_ascii=False, indent=2) if character_info else "无角色信息"}

### 章节信息
{json.dumps(chapter_summary, ensure_ascii=False, indent=2) if chapter_summary else "无章节信息"}

### 当前事件
{json.dumps(chapter_events, ensure_ascii=False, indent=2) if chapter_events else "无事件信息"}

### 跨章节记忆
{json.dumps(cross_chapter_memory, ensure_ascii=False, indent=2) if cross_chapter_memory else "无跨章节记忆"}

### 用户选择
{user_input}

### 选择评估
{json.dumps(evaluation, ensure_ascii=False, indent=2) if evaluation else "无评估信息"}

### 当前状态
- 当前进度：{current_progress}%
- 最近选择：{json.dumps(recent_choices, ensure_ascii=False, indent=2) if recent_choices else "无"}
- 故事偏离：{json.dumps(recent_divergences, ensure_ascii=False, indent=2) if recent_divergences else "无"}

### 场景生成指南
1. 必须严格从{character_name}的第一人称视角描述场景和内心感受
2. 创建一个有情感和细节的场景，但不要太冗长（200-300字）
3. 基于用户的选择，描述后续发展
4. 在关键情节点设计一个高自由度的交互
5. 不要提供固定选项，而是鼓励用户自由表达
6. 确保情绪状态和场景描述与角色身份一致
7. 必须描述用户扮演的对话者的反应、表情和态度变化，让他们像真实角色一样有个性
8. 环境应该随着情节的发展而变化，描述光线、气氛、声音等细节的变化
9. 交互对象的名字、特征和行为应该与故事情境保持一致
10. 保持与前面章节的情节连贯性，适当引用以前的关键事件
11. 在新情节与之前情节间建立合理的因果关联

请以JSON格式返回，包含以下字段：
- narrative: 从{character_name}第一人称视角的场景描述（必须使用"我"，不能用"{character_name}"），包含交互对象的反应和环境变化
- interaction_point: 需要用户互动的关键点描述
- context_hint: 给用户的提示，帮助他们理解当前情境
- key_elements: 当前场景中的3-5个关键元素（简短列表）
- emotion_state: 当前场景中主要角色的情感状态，包括交互对象的情绪
- memory_update: 应该被记住的关键事件或信息（1-3条简短描述）
- progress_info: {{
    "current_scene": "当前场景描述（简短）",
    "progress": 当前进度百分比（0-100）,
    "next_key_events": ["接下来可能发生的1-2个关键事件"]
}}"""
    
    def _build_initial_scene_prompt(self, character_name: str, current_chapter: int, interaction_id: str,
                               character_info: Dict[str, Any], chapter_summary: Dict[str, Any],
                               chapter_events: List[Dict[str, Any]], cross_chapter_memory: List[Dict[str, Any]],
                               perspective_instruction: str) -> str:
        """构建初始场景提示
        
        Returns:
            str: 提示词
        """
        return f"""你是一个沉浸式小说交互系统。生成一个章节的初始场景。严格遵循以下要求：

{perspective_instruction}

### 基本信息
- 角色：{character_name}
- 当前章节：{current_chapter}
- 交互ID：{interaction_id}

### 角色信息
{json.dumps(character_info, ensure_ascii=False, indent=2) if character_info else "无角色信息"}

### 章节信息
{json.dumps(chapter_summary, ensure_ascii=False, indent=2) if chapter_summary else "无章节信息"}

### 当前事件
{json.dumps(chapter_events, ensure_ascii=False, indent=2) if chapter_events else "无事件信息"}

### 跨章节记忆
{json.dumps(cross_chapter_memory, ensure_ascii=False, indent=2) if cross_chapter_memory else "无跨章节记忆"}

### 场景生成指南
1. 必须严格从{character_name}的第一人称视角描述场景和内心感受
2. 创建一个有情感和细节的场景，但不要太冗长（200-300字）
3. 描述章节开始时的情境，让用户了解当前处境
4. 在关键情节点设计一个高自由度的交互
5. 不要提供固定选项，而是鼓励用户自由表达
6. 确保情绪状态和场景描述与角色身份一致
7. 必须描述用户扮演的对话者的特征、外貌和态度，让他们像真实角色一样有个性
8. 环境描述应该具体且生动，包含光线、气氛、声音等细节
9. 交互对象的名字、特征和行为应该与故事情境保持一致
10. 保持与前面章节的情节连贯性，适当引用以前的关键事件
11. 如果是新章节，应简要回顾之前的关键剧情

请以JSON格式返回，包含以下字段：
- narrative: 从{character_name}第一人称视角的场景描述（必须使用"我"，不能用"{character_name}"），包含交互对象的特征和环境细节
- interaction_point: 需要用户互动的关键点描述
- context_hint: 给用户的提示，帮助他们理解当前情境
- key_elements: 当前场景中的3-5个关键元素（简短列表）
- emotion_state: 当前场景中主要角色的情感状态，包括交互对象的情绪
- memory_update: 应该被记住的关键事件或信息（1-3条简短描述）
- progress_info: {{
    "current_scene": "当前场景描述（简短）",
    "progress": 0,
    "next_key_events": ["接下来可能发生的1-2个关键事件"]
}}"""
    
    def _validate_first_person_perspective(self, text: str, character_name: str) -> bool:
        """验证文本是否使用第一人称视角
        
        Args:
            text: 文本内容
            character_name: 角色名称
            
        Returns:
            bool: 是否是第一人称视角
        """
        # 检查是否包含"我"而不是角色名称作为主语
        has_first_person = "我" in text and "我的" in text
        has_character_name_as_subject = re.search(f"{character_name}[^，。；：？！]*[是|走|看|说|想|感觉|觉得]", text) is not None
        
        # 返回是否是第一人称视角
        return has_first_person and not has_character_name_as_subject
    
    def _fix_perspective(self, text: str, character_name: str) -> str:
        """修正文本为第一人称视角
        
        Args:
            text: 文本内容
            character_name: 角色名称
            
        Returns:
            str: 修正后的文本
        """
        # 简单替换角色名称为"我"
        fixed_text = re.sub(f"{character_name}(?![^，。；：？！]*的)", "我", text)
        fixed_text = re.sub(f"{character_name}的", "我的", fixed_text)
        
        return fixed_text 