from typing import Dict, List, Optional
import logging
from pathlib import Path
import json
from openai import OpenAI
from datetime import datetime
from functools import wraps
import time
import re

from .document import NovelProcessor
from .knowledge import KnowledgeBase, StoryContext
from config.config import settings

logger = logging.getLogger(__name__)

def handle_llm_response(func):
    """装饰器：处理LLM响应的通用逻辑"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, str) and (result.startswith('```') and result.endswith('```')):
                result = result.split('\n', 1)[1].rsplit('\n', 1)[0]
            return json.loads(result) if isinstance(result, str) else result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response in {func.__name__}: {e}")
            return func.default_response if hasattr(func, 'default_response') else {}
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            return func.default_response if hasattr(func, 'default_response') else {}
    return wrapper

class CharacterInteraction:
    """角色互动系统"""
    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.knowledge_base = KnowledgeBase(novel_id)
        self.story_context = StoryContext(self.knowledge_base)
        self.interaction_state = InteractionState(novel_id)
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )
        # 初始化知识库
        self.initialize_knowledge_base()
        
    def initialize_from_processor(self, processor: NovelProcessor) -> None:
        """从文档处理器初始化知识库"""
        try:
            # 初始化知识库
            self.knowledge_base.initialize()
            
            # 添加每个章节的知识
            for chapter in processor.chapters:
                # 获取章节元数据
                metadata_file = settings.DATA_DIR / 'novels' / self.novel_id / 'metadata' / f'metadata_{chapter.number:03d}.json'
                logger.info(f"Looking for metadata file: {metadata_file}")
                
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        logger.info(f"Loading metadata for chapter {chapter.number}")
                        logger.debug(f"Metadata content: {json.dumps(metadata, ensure_ascii=False, indent=2)}")
                        self.knowledge_base.add_chapter_knowledge(chapter.number, metadata)
                else:
                    logger.warning(f"Metadata file not found: {metadata_file}")
                        
            logger.info(f"Successfully initialized knowledge base for novel {self.novel_id}")
            
            # 打印已加载的角色信息
            logger.info("Loaded characters:")
            for char_name, char_data in self.knowledge_base.characters.items():
                logger.info(f"Character: {char_name}")
                logger.info(f"Appearances in chapters: {char_data.appearances}")
            
        except Exception as e:
            logger.error(f"Error initializing knowledge base: {str(e)}")
            raise

    def initialize_knowledge_base(self) -> None:
        """初始化知识库和交互状态，确保有足够的世界信息"""
        try:
            # 初始化知识库
            self.knowledge_base.initialize()
            
            # 手动加载所有章节的元数据和摘要
            for chapter_num in range(1, 51):  # 最多支持50章，可按需调整
                chapter_idx = chapter_num - 1
                
                # 加载元数据
                metadata_file = settings.DATA_DIR / 'novels' / self.novel_id / 'metadata' / f'metadata_{chapter_num:03d}.json'
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        try:
                            metadata = json.load(f)
                            self.knowledge_base.add_chapter_knowledge(chapter_idx, metadata)
                            logger.info(f"加载第{chapter_num}章元数据成功")
                        except json.JSONDecodeError:
                            logger.error(f"metadata文件格式错误: {metadata_file}")
                        except Exception as e:
                            logger.error(f"加载metadata时出错: {str(e)}")
                else:
                    # 如果找不到更多章节，假设已经加载完毕
                    if chapter_num > 3:  # 至少应该有几章
                        break
            
            # 加载世界观元数据（如果存在）
            world_metadata_file = settings.DATA_DIR / 'novels' / self.novel_id / 'metadata' / 'world_metadata.json'
            if world_metadata_file.exists():
                with open(world_metadata_file, 'r', encoding='utf-8') as f:
                    try:
                        world_metadata = json.load(f)
                        self.knowledge_base.add_world_knowledge(world_metadata)
                        logger.info("加载世界观元数据成功")
                    except Exception as e:
                        logger.error(f"加载世界观元数据失败: {str(e)}")
            
            # 预载入摘要内容
            self._load_all_summaries()
            
            logger.info(f"成功初始化知识库和交互状态")
        except Exception as e:
            logger.error(f"初始化知识库失败: {str(e)}")
            raise

    def _load_all_summaries(self) -> None:
        """预加载所有章节摘要"""
        summaries_dir = settings.DATA_DIR / 'novels' / self.novel_id / 'summaries'
        if not summaries_dir.exists():
            logger.warning(f"摘要目录不存在: {summaries_dir}")
            return
        
        try:
            summary_files = sorted(summaries_dir.glob("summary_*.txt"))
            for summary_file in summary_files:
                try:
                    chapter_num = int(summary_file.stem.split('_')[1])
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary_content = f.read().strip()
                        # 将摘要存储到内存中，方便后续使用
                        self.knowledge_base.add_chapter_summary(chapter_num - 1, summary_content)
                    logger.info(f"加载第{chapter_num}章摘要成功")
                except Exception as e:
                    logger.error(f"加载摘要文件失败 {summary_file}: {str(e)}")
        except Exception as e:
            logger.error(f"加载摘要文件时出错: {str(e)}")

    def start_interaction(self, character_name: str, chapter: int) -> Dict:
        """开始角色互动"""
        try:
            # 打印当前知识库状态
            logger.info(f"Current characters in knowledge base: {list(self.knowledge_base.characters.keys())}")
            logger.info(f"Attempting to interact with character '{character_name}' in chapter {chapter}")
            
            # 更新故事上下文
            self.story_context.update_context(
                chapter=chapter,
                characters=[character_name]
            )
            
            # 获取角色上下文
            character_context = self.knowledge_base.get_character_context(
                character_name, 
                chapter
            )
            
            if not character_context:
                logger.error(f"Character context not found. Available characters: {list(self.knowledge_base.characters.keys())}")
                raise ValueError(f"Character {character_name} not found in chapter {chapter}")
                
            # 获取相关知识
            relevant_knowledge = self.story_context.get_relevant_knowledge(
                query=f"关于{character_name}在第{chapter}章的情况",
                top_k=3
            )
            
            # 构建角色状态
            return {
                'character': character_context,
                'current_chapter': chapter,
                'relevant_knowledge': relevant_knowledge
            }
            
        except Exception as e:
            logger.error(f"Error starting interaction: {str(e)}")
            raise
            
    def generate_response(self, character_name: str, user_input: str, interaction_state: Dict) -> str:
        """生成角色回应"""
        try:
            # 处理交互状态，确保可以序列化为JSON
            safe_interaction_state = {
                'character': self._make_json_safe(interaction_state['character']) if isinstance(interaction_state.get('character'), dict) else {},
                'current_chapter': interaction_state.get('current_chapter'),
                'relevant_knowledge': self._make_json_safe(interaction_state['relevant_knowledge']) if isinstance(interaction_state.get('relevant_knowledge'), (list, dict)) else []
            }

            # 构建提示
            messages = [
                {
                    "role": "system",
                    "content": f"""你现在扮演小说中的角色 {character_name}。
                    基于以下角色信息和上下文进行回答：
                    
                    角色信息：
                    {json.dumps(safe_interaction_state['character'], ensure_ascii=False, indent=2)}
                    
                    当前章节：{safe_interaction_state['current_chapter']}
                    
                    相关知识：
                    {json.dumps(safe_interaction_state['relevant_knowledge'], ensure_ascii=False, indent=2)}
                    
                    请以第一人称的方式回答，保持角色性格特征的一致性。回答要符合当前章节的剧情发展，
                    不要透露未来的剧情。语气和措辞要符合角色的身份和性格。"""
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ]
            
            # 调用API生成回复
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "对不起，我现在无法回答。"

    def _collect_world_knowledge(self, chapter: int) -> Dict:
        """收集世界观相关的元数据"""
        world_knowledge = {
            'characters': {},
            'locations': {},
            'events': [],
            'rules': {},
            'relationships': {},
            'items': {}
        }
        
        # 收集角色信息
        for char_name in self.knowledge_base.characters:
            char_info = self.knowledge_base.get_character_context(char_name, chapter)
            if char_info:
                world_knowledge['characters'][char_name] = {
                    'description': char_info['basic_info']['description'],
                    'traits': char_info['basic_info']['traits'],
                    'relationships': char_info['relationships'],
                    'development': char_info['development_history']
                }
        
        # 收集地点信息
        for loc_name, loc_data in self.knowledge_base.locations.items():
            world_knowledge['locations'][loc_name] = {
                'description': loc_data.description,
                'atmosphere': loc_data.atmosphere,
                'events': loc_data.events
            }
        
        # 收集事件信息
        for event in self.knowledge_base.events:
            if event.chapter <= chapter:
                world_knowledge['events'].append({
                    'description': event.description,
                    'importance': event.importance,
                    'characters': event.characters,
                    'location': event.location,
                    'consequences': event.consequences
                })
                
        return world_knowledge

    def evaluate_choice(self, choice: Dict, current_chapter: int, character_name: str, story_state: Dict, is_immersive: bool = False) -> Dict:
        """评估用户选择的影响（整合了普通选择和沉浸式选择的评估）"""
        try:
            # 获取当前章节和角色信息
            character_info = self.knowledge_base.get_character_context(character_name, current_chapter)
            world_knowledge = self._collect_world_knowledge(current_chapter)
            
            # 构建评估提示
            evaluation_template = {
                "is_valid": True,
                "impact_level": 0,
                "character_impact": "",
                "story_progress": 0,
                "relationship_changes": {},
                "consequences": "",
                "next_scene_hint": "",
                "world_impact": {
                    "immediate": [],
                    "long_term": []
                }
            }
            
            prompt = f"""作为故事的评估者，请分析用户的选择对故事发展的影响。

角色信息：
{json.dumps(character_info, ensure_ascii=False, indent=2)}

世界观信息：
{json.dumps(world_knowledge, ensure_ascii=False, indent=2)}

当前状态：
{json.dumps(story_state, ensure_ascii=False, indent=2)}

用户选择：
{json.dumps(choice, ensure_ascii=False, indent=2)}

请评估：
1. 选择的合理性：是否符合角色设定和当前处境
2. 对角色的影响：这个选择如何影响角色的心理和处境
3. 对剧情的影响：这个选择会如何推动或改变故事发展
4. 对关系的影响：这个选择如何影响与其他角色的关系
5. 后续发展：这个选择可能带来的后续情节发展

请以JSON格式返回评估结果，包含以下字段：
{json.dumps(evaluation_template, ensure_ascii=False, indent=2)}"""

            # 调用API进行评估
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.4,
                max_tokens=1000
            )
            
            evaluation = handle_llm_response(lambda: response.choices[0].message.content)()
            
            # 更新交互状态
            if evaluation.get('is_valid', False):
                self.interaction_state.add_user_choice(current_chapter, {
                    'content': choice,
                    'impact': evaluation.get('character_impact', ''),
                    'consequences': evaluation.get('consequences', '')
                })
                
                # 如果有重大影响，记录故事偏离
                if evaluation.get('impact_level', 0) >= 4:
                    self.interaction_state.add_story_divergence(current_chapter, {
                        'point': choice,
                        'reason': evaluation.get('character_impact', ''),
                        'impact': evaluation.get('consequences', '')
                    })
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating choice: {str(e)}")
            return {
                "is_valid": True,
                "impact_level": 1,
                "character_impact": "无法确定影响",
                "story_progress": current_chapter,
                "relationship_changes": {},
                "consequences": "继续观察",
                "next_scene_hint": "保持当前方向",
                "world_impact": {
                    "immediate": [],
                    "long_term": []
                }
            }

    def generate_scene(self, chapter: int, character_name: str, story_state: Dict, is_immersive: bool = False) -> Dict:
        """生成场景描述（整合了普通场景和沉浸式场景的生成）"""
        try:
            # 获取必要信息
            chapter_info = self.knowledge_base.get_character_context(character_name, chapter)
            current_state = self.interaction_state.get_chapter_state(chapter)
            character_development = self.interaction_state.get_character_development(character_name)
            world_knowledge = self._collect_world_knowledge(chapter)
            
            # 初始场景处理：如果是角色首次出现，需要获取更多背景信息
            is_first_interaction = not story_state.get('previous_responses')
            need_original_text = is_first_interaction  # 首次交互默认需要原文作为参考
            
            # 获取交互情境：是新场景还是继续上次交互
            is_continuation = story_state.get('previous_responses', []) and story_state.get('last_interaction_id')
            last_response = story_state.get('previous_responses', [])[-1] if story_state.get('previous_responses') else None
            
            # 定义场景模板
            scene_template = {
                "narrative": "",
                "environment": "",
                "character_state": "",
                "other_characters": [],
                "atmosphere": "",
                "key_elements": [],
                "interaction_points": [],
                "interaction_id": str(int(time.time())),  # 用于标识本次交互
                "progress_info": {
                    "current_scene": "",
                    "completed_plot_points": [],
                    "progress_percentage": 0,
                    "next_key_events": [],
                    "chapter_completion_conditions": [],
                    "can_proceed_to_next": False
                }
            }

            # 构建场景生成提示
            # 视角说明：确保从所选角色的视角出发
            perspective_instruction = f"""重要：玩家已选择扮演角色"{character_name}"，所有内容必须从"{character_name}"的第一人称视角生成。
使用"我"而不是"你"来指代{character_name}，将其他角色作为"你"或使用他们的名字来指代。
描述应反映{character_name}看到、听到、感受到的一切，体现{character_name}的思想和感受。"""
            
            # 交互连续性提示
            continuation_prompt = ""
            if is_continuation and last_response:
                continuation_prompt = f"""
上次交互情况：
- 用户角色选择: {last_response.get('response', '未记录')}
- 系统评估: {json.dumps(last_response.get('evaluation', {}), ensure_ascii=False)}

请基于用户的上次选择继续推进故事情节，生成新的交互点。
"""

            # 初始化背景提示 - 优化为只提供关键背景信息
            init_background = ""
            if is_first_interaction:
                # 确定角色首次出现的章节
                first_appearance_chapter = -1
                for char_name, char_data in self.knowledge_base.characters.items():
                    if char_name == character_name and char_data.appearances:
                        first_appearance_chapter = min(char_data.appearances)
                        break
                
                # 如果找到角色首次出现的章节，且当前章节就是该章节
                if first_appearance_chapter >= 0 and first_appearance_chapter == chapter:
                    # 获取角色首次出现前的关键背景信息（而不是所有章节内容）
                    background_summary = self._get_condensed_background(first_appearance_chapter)
                    
                    if background_summary:
                        init_background = f"""
重要背景信息：
{background_summary}

请基于以上背景信息，从{character_name}的第一人称视角生成角色首次登场的场景。描述应该与原著情节相符，但必须从{character_name}的视角出发。
"""

            prompt = f"""你是一个{'沉浸式' if is_immersive else ''}小说交互系统。请基于以下信息生成场景描述：

{perspective_instruction}

当前角色：{character_name}
当前章节：{chapter + 1}  # 用户友好的章节编号（从1开始）

角色信息：{json.dumps(chapter_info, ensure_ascii=False, indent=2)}

世界观信息：
{json.dumps(self._get_essential_world_knowledge(world_knowledge), ensure_ascii=False, indent=2)}

当前交互状态：
- 已完成的情节：{json.dumps(current_state['completed_plot_points'], ensure_ascii=False)}
- 当前场景：{current_state['current_scene']}
- 进度：{current_state['progress_percentage']}%
- 与原文的偏离：{json.dumps(current_state.get('divergences', []), ensure_ascii=False)}
- 角色发展变化：{json.dumps(character_development, ensure_ascii=False)}

{init_background}
{continuation_prompt}

请注意以下要求：
1. 必须从{character_name}的第一人称视角描述场景，使用"我"来表示{character_name}
2. 描述{character_name}看到、听到和感受到的环境、氛围和其他角色
3. 在一个章节中设计多个交互点，每个交互点应该是故事情节中的关键时刻
4. 每个交互点应允许高自由度的用户输入，符合{character_name}的视角和选择
5. 确保描述符合{character_name}的性格特征和行为方式
6. 评估当前进度并与原著情节对比
7. 如果你需要查看原文内容以确保故事的准确性，请在response中添加need_original_text=true

请以JSON格式返回，包含以下字段：
{json.dumps(scene_template, ensure_ascii=False, indent=2)}"""

            # 如果是首次交互或LLM明确需要原文，获取原文内容
            if need_original_text:
                chapter_content = self._get_chapter_content(chapter)
                if chapter_content:
                    prompt += f"\n\n原文内容：\n{chapter_content}"
            
            # 调用API生成场景
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            scene = handle_llm_response(lambda: response.choices[0].message.content)()
            
            # 如果LLM表示需要查看原文但尚未提供
            if scene.get('need_original_text', False) and not need_original_text:
                logger.info("LLM请求查看原文内容，重新生成交互")
                # 获取章节原文
                chapter_content = self._get_chapter_content(chapter)
                prompt += f"\n\n原文内容：\n{chapter_content}"
                
                # 重新生成
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2000
                )
                
                scene = handle_llm_response(lambda: response.choices[0].message.content)()
            
            # 更新交互状态
            if 'progress_info' in scene:
                self.interaction_state.update_chapter_state(chapter, scene['progress_info'])
            
            return scene
            
        except Exception as e:
            logger.error(f"Error generating scene: {str(e)}")
            return {
                "narrative": "场景继续展开...",
                "environment": "当前环境",
                "character_state": "保持观察",
                "other_characters": [],
                "atmosphere": "不确定",
                "key_elements": [],
                "interaction_points": [
                    {"type": "observation", "description": "继续观察周围"},
                    {"type": "action", "description": "保持警觉"}
                ],
                "interaction_id": str(int(time.time())),
                "progress_info": {
                    "current_scene": "场景继续",
                    "completed_plot_points": [],
                    "progress_percentage": 0,
                    "next_key_events": [],
                    "chapter_completion_conditions": ["继续当前情节"],
                    "can_proceed_to_next": False
                }
            }

    def _get_condensed_background(self, target_chapter: int) -> str:
        """获取特定章节之前的精简背景信息"""
        if target_chapter <= 0:
            return ""
        
        # 只获取关键的背景信息，而不是所有章节的摘要
        condensed_info = []
        
        # 1. 获取主要角色和地点信息
        main_characters = {}
        main_locations = {}
        important_events = []
        
        # 收集主要角色、地点和事件
        for chapter_idx in range(target_chapter):
            # 收集重要事件
            for event in self.knowledge_base.events:
                if event.chapter == chapter_idx and event.importance >= 3:  # 只收集重要性较高的事件
                    important_events.append({
                        'chapter': chapter_idx + 1,
                        'description': event.description
                    })
                    
                    # 添加与事件相关的主要角色
                    for char_name in event.characters:
                        if char_name in self.knowledge_base.characters:
                            char = self.knowledge_base.characters[char_name]
                            main_characters[char_name] = char.description
                    
                    # 添加事件发生的地点
                    if event.location in self.knowledge_base.locations:
                        loc = self.knowledge_base.locations[event.location]
                        main_locations[event.location] = loc.description
        
        # 2. 格式化背景信息
        if main_characters:
            char_info = "\n".join([f"- {name}: {desc}" for name, desc in main_characters.items()])
            condensed_info.append(f"主要角色:\n{char_info}")
        
        if main_locations:
            loc_info = "\n".join([f"- {name}: {desc}" for name, desc in main_locations.items()])
            condensed_info.append(f"重要地点:\n{loc_info}")
        
        if important_events:
            event_info = "\n".join([f"- 第{event['chapter']}章: {event['description']}" for event in important_events])
            condensed_info.append(f"关键事件:\n{event_info}")
        
        # 3. 如果上述信息不足，尝试添加最后一章的摘要
        if not condensed_info and target_chapter > 0:
            last_chapter_summary = self._get_chapter_summary(target_chapter - 1)
            if last_chapter_summary:
                condensed_info.append(f"前情概要:\n{last_chapter_summary}")
        
        return "\n\n".join(condensed_info)

    def _get_essential_world_knowledge(self, world_knowledge: Dict) -> Dict:
        """获取精简的世界知识，减少token使用"""
        essential_knowledge = {
            'characters': {},
            'locations': {},
            'events': [],
            'rules': world_knowledge.get('rules', {}),
            'relationships': world_knowledge.get('relationships', {})
        }
        
        # 只保留主要角色信息（最多5个）
        characters = world_knowledge.get('characters', {})
        sorted_chars = sorted(
            characters.items(), 
            key=lambda x: len(x[1].get('relationships', [])) + len(x[1].get('development', [])), 
            reverse=True
        )
        for name, info in sorted_chars[:5]:  # 只保留5个最重要的角色
            essential_knowledge['characters'][name] = {
                'description': info.get('description', ''),
                'traits': info.get('traits', []),
                'relationships': info.get('relationships', [])
            }
        
        # 只保留当前相关的地点信息（最多3个）
        locations = world_knowledge.get('locations', {})
        sorted_locs = sorted(
            locations.items(),
            key=lambda x: len(x[1].get('events', [])),
            reverse=True
        )
        for name, info in sorted_locs[:3]:  # 只保留3个最重要的地点
            essential_knowledge['locations'][name] = {
                'description': info.get('description', ''),
                'atmosphere': info.get('atmosphere', '')
            }
        
        # 只保留重要事件（最多5个）
        events = world_knowledge.get('events', [])
        sorted_events = sorted(
            events,
            key=lambda x: x.get('importance', 0),
            reverse=True
        )
        essential_knowledge['events'] = sorted_events[:5]  # 只保留5个最重要的事件
        
        return essential_knowledge

    def _get_chapter_summary(self, chapter_number: int) -> str:
        """获取章节摘要内容"""
        # 先从知识库中获取摘要
        summary = self.knowledge_base.get_chapter_summary(chapter_number)
        if summary:
            return summary
            
        # 如果知识库中没有，尝试从文件读取
        chapter_num = str(chapter_number + 1).zfill(3)  # 转换为三位数格式 (001, 002, etc.)
        summary_path = settings.DATA_DIR / 'novels' / self.novel_id / "summaries" / f"summary_{chapter_num}.txt"
        try:
            if summary_path.exists():
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_content = f.read().strip()
                    # 保存到知识库中
                    self.knowledge_base.add_chapter_summary(chapter_number, summary_content)
                    return summary_content
        except Exception as e:
            logger.error(f"Error reading summary file {summary_path}: {str(e)}")
        return ""

    def _get_chapter_content(self, chapter_number: int) -> str:
        """获取章节原文内容"""
        chapter_file = settings.DATA_DIR / 'chapters' / 'temp_sample_xiaowangzi' / f"chapter_{chapter_number:03d}.txt"
        if chapter_file.exists():
            with open(chapter_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def generate_story_interaction(self, chapter: int, character_name: str, story_state: Dict) -> Dict:
        """基于原文生成故事交互点，支持多交互点和第一人称视角"""
        try:
            # 获取相关章节信息和世界知识
            current_chapter_number = chapter
            interaction_id = f"ch{chapter}_{int(time.time())}"  # 生成唯一交互ID
            
            # 获取角色信息
            character_info = self.knowledge_base.get_character_context(character_name, current_chapter_number)
            
            # 检查角色是否在当前章节登场
            if not character_info or current_chapter_number not in character_info.get('appearances', []):
                logger.warning(f"角色 {character_name} 在第 {current_chapter_number} 章未登场，使用前文信息")
            
            # 获取当前章节摘要
            chapter_summary = self._get_chapter_summary(current_chapter_number)
            
            # 获取已经完成的交互点
            completed_interactions = self.interaction_state.get_completed_interaction_points(current_chapter_number)
            
            # 获取当前交互状态
            current_state = self.interaction_state.get_chapter_state(current_chapter_number)
            character_development = self.interaction_state.get_character_development(character_name)
            
            # 检查故事偏离情况
            divergences = current_state.get('divergences', [])
            story_divergence_level = len(divergences)
            
            # 计算查询原文的需求
            need_original_text = (
                story_divergence_level > 2 or  # 如果偏离度高
                len(completed_interactions) == 0  # 如果是章节第一次交互
            )
            
            # 注册新的交互点
            self.interaction_state.register_interaction_point(
                current_chapter_number, 
                interaction_id,
                options=None  # 开放式交互不预设选项
            )
            
            # 构建提示词
            prompt = f"""你是一个沉浸式小说交互系统。生成一个与用户的故事交互场景，严格遵循以下要求：

角色视角：{character_name}（必须使用第一人称"我"讲述）
当前章节：{current_chapter_number}
交互ID：{interaction_id}

### 角色信息
{json.dumps(character_info, ensure_ascii=False, indent=2)}

### 当前章节摘要
{chapter_summary}

### 交互状态
- 已完成的交互点：{json.dumps(completed_interactions, ensure_ascii=False)}
- 当前进度：{current_state.get('progress', 0)}%
- 故事偏离：{'高' if story_divergence_level > 1 else '低'}
- 偏离详情：{json.dumps(divergences[-2:] if len(divergences) > 2 else divergences, ensure_ascii=False)}
- 角色发展变化：{json.dumps(character_development[-2:] if len(character_development) > 2 else character_development, ensure_ascii=False)}

### 交互生成指南
1. 必须严格从{character_name}的第一人称视角描述场景和内心感受
2. 创建一个有情感和细节的场景，但不要太冗长（200-300字）
3. 基于章节进度和当前情境，在关键情节点设计一个高自由度的交互
4. 不要提供固定选项，而是鼓励用户自由表达
5. 交互点应该自然融入故事情节，避免生硬的选择题模式
6. 确保情绪状态和场景描述与角色身份一致

{f'7. 请参考以下原文内容确保故事方向正确：\n{self._get_chapter_content(current_chapter_number)[:500]}...' if need_original_text else ''}

请以JSON格式返回，包含以下字段：
- narrative: 从{character_name}第一人称视角的场景描述（必须使用"我"，不能用"{character_name}"）
- interaction_point: 需要用户互动的关键点描述
- context_hint: 给用户的提示，帮助他们理解当前情境
- key_elements: 当前场景中的3-5个关键元素（简短列表）
- emotion_state: 当前场景中主要角色的情感状态
- progress_info: {{
    "current_scene": "当前场景描述（简短）",
    "progress": 当前进度百分比（0-100）,
    "next_key_events": ["接下来可能发生的1-2个关键事件"]
}}"""

            # 构建消息并调用API
            messages = [{"role": "system", "content": prompt}]
            
            # 调用API生成场景
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )
            
            try:
                content = response.choices[0].message.content
                # 处理可能的markdown代码块
                if content.startswith('```') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                
                scene = json.loads(content)
                
                # 验证视角是否正确（必须是第一人称）
                narrative = scene.get('narrative', '')
                if not self._validate_first_person_perspective(narrative, character_name):
                    logger.warning("生成的内容不是第一人称视角，进行修正")
                    # 修正视角
                    scene['narrative'] = self._fix_perspective(narrative, character_name)
                
                # 确保情感状态使用正确的第一人称称谓
                if isinstance(scene.get('emotion_state'), dict):
                    emotion_state = scene['emotion_state']
                    if character_name in emotion_state:
                        emotion_state['我'] = emotion_state.pop(character_name)
                
                # 更新交互状态
                if 'progress_info' in scene:
                    self.interaction_state.update_chapter_state(current_chapter_number, scene['progress_info'])
                
                # 添加交互ID以便跟踪
                scene['interaction_id'] = interaction_id
                
                return scene
                
            except json.JSONDecodeError as e:
                logger.error(f"解析场景生成响应失败: {e}")
                logger.error(f"响应内容: {response.choices[0].message.content}")
                # 返回一个基本的回退场景
                return {
                    "narrative": f"我（{character_name}）站在这里，思考着接下来该怎么做。",
                    "interaction_point": "我需要做出一个决定...",
                    "context_hint": "考虑当前的情况，我可以怎么行动？",
                    "key_elements": ["我", "当前环境", "面临的选择"],
                    "emotion_state": {"我": "思考中"},
                    "interaction_id": interaction_id,
                    "progress_info": {
                        "current_scene": "继续故事",
                        "progress": current_state.get('progress', 0),
                        "next_key_events": ["故事发展"]
                    }
                }
                
        except Exception as e:
            logger.error(f"生成故事交互失败: {str(e)}")
            raise
            
    def _validate_first_person_perspective(self, text: str, character_name: str) -> bool:
        """验证文本是否使用第一人称视角"""
        # 检查是否包含"我"而不是角色名称作为主语
        has_first_person = "我" in text and "我的" in text
        has_character_name_as_subject = re.search(f"{character_name}[^，。；：？！]*[是|走|看|说|想|感觉|觉得]", text) is not None
        
        # 返回是否是第一人称视角
        return has_first_person and not has_character_name_as_subject
        
    def _fix_perspective(self, text: str, character_name: str) -> str:
        """修正文本为第一人称视角"""
        # 简单替换角色名称为"我"
        fixed_text = re.sub(f"{character_name}(?![^，。；：？！]*的)", "我", text)
        fixed_text = re.sub(f"{character_name}的", "我的", fixed_text)
        
        return fixed_text

    def evaluate_story_response(self, response: str, current_chapter: int, character_name: str, story_state: Dict, current_scene: Dict) -> Dict:
        """评估玩家的回应并推进故事"""
        try:
            # 获取当前章节和角色信息
            character_info = self.knowledge_base.get_character_context(character_name, current_chapter)
            world_knowledge = self._collect_world_knowledge(current_chapter)
            
            # 构建评估提示
            messages = [
                {
                    "role": "system",
                    "content": f"""作为故事的引导者，请评估玩家的回应并决定如何推进故事。

当前情节：
{json.dumps(current_scene, ensure_ascii=False, indent=2)}

角色信息：
{json.dumps(character_info, ensure_ascii=False, indent=2)}

世界观信息：
{json.dumps(world_knowledge, ensure_ascii=False, indent=2)}

玩家回应：
{response}

故事状态：
{json.dumps(story_state, ensure_ascii=False, indent=2)}

请进行详细评估：
1. 评估回应是否符合角色特点和当前情境
2. 这个回应是否符合故事的世界观设定
3. 这个回应对故事线的影响程度（是否导致剧情偏离）
4. 这个回应如何影响角色关系和情感状态
5. 确定故事是否应该推进到新的情节点
6. 如果需要查看原文内容来确定评估准确性，请在response中添加need_original_text=true

请以JSON格式返回评估结果，包含以下字段：
- is_appropriate: 回应是否合适（布尔值）
- world_consistency: 与世界观的一致性评分（0-10）
- character_consistency: 与角色设定的一致性评分（0-10）
- divergence_level: 与原故事情节的偏离程度（0-10）
- story_impact: 对故事的影响描述
- relationship_changes: 对角色关系的影响
- emotion_changes: 情感变化描述
- narrative_response: 故事对玩家回应的反馈
- should_progress: 是否应该推进到新的情节（布尔值）
- next_interaction_hint: 下一个交互点的提示
- need_original_text: 是否需要查看原文内容（布尔值）
"""
                }
            ]
            
            # 调用API进行评估
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.4,
                max_tokens=1500
            )
            
            evaluation = handle_llm_response(lambda: response.choices[0].message.content)()
            
            # 如果LLM表示需要查看原文
            if evaluation.get('need_original_text', False):
                logger.info("LLM请求查看原文内容，重新评估回应")
                # 获取章节原文
                chapter_content = self._get_chapter_content(current_chapter)
                messages[0]["content"] += f"\n\n原文内容：\n{chapter_content}"
                
                # 重新评估
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=0.4,
                    max_tokens=1500
                )
                
                evaluation = handle_llm_response(lambda: response.choices[0].message.content)()
            
            # 更新交互状态
            if evaluation.get('is_appropriate', True):
                # 记录用户选择及其影响
                self.interaction_state.add_user_choice(current_chapter, {
                    'content': response,
                    'impact': evaluation.get('story_impact', ''),
                    'divergence_level': evaluation.get('divergence_level', 0)
                })
                
                # 如果偏离严重，记录故事偏离
                if evaluation.get('divergence_level', 0) >= 7:
                    self.interaction_state.add_story_divergence(current_chapter, {
                        'point': response,
                        'reason': evaluation.get('story_impact', ''),
                        'impact': evaluation.get('divergence_level', 0)
                    })
                
                # 更新角色关系变化
                if evaluation.get('relationship_changes'):
                    for char, change in evaluation.get('relationship_changes', {}).items():
                        self.interaction_state.update_character_development(char, {
                            'chapter': current_chapter,
                            'change': change,
                            'reason': response
                        })
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating story response: {str(e)}")
            return {
                "is_appropriate": True,
                "world_consistency": 8,
                "character_consistency": 8,
                "divergence_level": 2,
                "story_impact": "继续观察",
                "relationship_changes": {},
                "emotion_changes": "状态未变",
                "narrative_response": "继续...",
                "should_progress": False,
                "next_interaction_hint": "继续当前对话",
                "need_original_text": False
            }

    def _make_json_safe(self, obj):
        """递归地将对象转换为JSON安全的格式"""
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        elif isinstance(obj, dict):
            return {
                str(k): self._make_json_safe(v)
                for k, v in obj.items()
                if not k.startswith('_')  # 跳过私有属性
            }
        elif hasattr(obj, '__dict__'):
            return self._make_json_safe(obj.__dict__)
        else:
            return str(obj)  # 将其他类型转换为字符串
            
    def update_interaction_state(self, 
                               character_name: str, 
                               chapter: int, 
                               interaction_state: Dict) -> Dict:
        """更新互动状态"""
        # 获取最新的角色上下文
        character_context = self.knowledge_base.get_character_context(
            character_name, 
            chapter
        )
        
        # 获取最新的相关知识
        relevant_knowledge = self.story_context.get_relevant_knowledge(
            query=f"关于{character_name}在第{chapter}章的最新情况",
            top_k=3
        )
        
        # 更新状态
        interaction_state.update({
            'character': character_context,
            'current_chapter': chapter,
            'relevant_knowledge': relevant_knowledge
        })
        
        return interaction_state 

    def generate_immersive_scene(self, chapter: int, character_name: str, story_state: Dict) -> Dict:
        """生成沉浸式场景描述和选择"""
        try:
            # 获取章节信息和角色信息
            chapter_info = self.knowledge_base.get_character_context(character_name, chapter)
            
            # 视角说明：确保从所选角色的视角出发
            perspective_instruction = f"""重要：玩家已选择扮演角色"{character_name}"，所有内容必须从"{character_name}"的第一人称视角生成。
使用"我"而不是"你"来指代{character_name}，将其他角色作为"你"或使用他们的名字来指代。
描述应反映{character_name}看到、听到、感受到的一切，体现{character_name}的思想和感受。"""
            
            # 构建场景生成提示
            messages = [
                {
                    "role": "system",
                    "content": f"""你现在是一个沉浸式小说体验系统。请基于以下信息，生成一个让玩家身临其境的场景描述：

{perspective_instruction}

当前角色：{character_name}
当前章节：{chapter + 1}
角色信息：{json.dumps(chapter_info, ensure_ascii=False, indent=2)}
故事状态：{json.dumps(story_state, ensure_ascii=False, indent=2)}

请从以下几个方面描述场景：
1. 从{character_name}的第一人称视角（"我"）详细描述周围的环境，包括视觉、听觉、嗅觉等感官细节
2. 描述{character_name}（"我"）当前的心理和生理状态
3. 描述场景中其他角色的状态和行为（从{character_name}的视角看到的）
4. 描述场景中的重要物品或线索
5. 描述场景的整体氛围和情绪

然后，基于当前场景和{character_name}的特点，生成3-5个符合{character_name}身份和处境的选择。这些选择应该：
- 符合{character_name}的性格和能力
- 能推动故事发展
- 具有不同的风险和收益
- 反映{character_name}的内心挣扎或目标

请以JSON格式返回，包含以下字段：
- narrative: 场景叙述（从{character_name}的第一人称视角）
- environment: 环境描述
- character_state: 角色状态
- other_characters: 其他角色的描述
- atmosphere: 场景氛围
- choices: 可选行动列表（每个选项都应该包含行动描述和可能的影响）
"""
                }
            ]
            
            # 调用API生成场景
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.8,  # 增加创造性
                max_tokens=2000    # 允许更长的响应
            )
            
            try:
                scene = json.loads(response.choices[0].message.content)
                return scene
            except json.JSONDecodeError:
                logger.error("Failed to parse scene generation response")
                return {
                    "narrative": "我发现自己置身于故事之中...",
                    "environment": "当前场景",
                    "character_state": "我感到有些困惑",
                    "other_characters": [],
                    "atmosphere": "神秘",
                    "choices": [
                        {"action": "继续观察周围", "impact": "了解更多信息"},
                        {"action": "思考我的处境", "impact": "整理思绪"},
                        {"action": "寻找线索", "impact": "可能发现重要信息"}
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error generating immersive scene: {str(e)}")
            return {
                "narrative": "我的思绪有些混乱...",
                "environment": "模糊不清",
                "character_state": "我感到困惑",
                "other_characters": [],
                "atmosphere": "不确定",
                "choices": [
                    {"action": "集中注意力", "impact": "理清当前处境"},
                    {"action": "保持冷静", "impact": "等待局势明朗"},
                    {"action": "回想发生了什么", "impact": "寻找线索"}
                ]
            }

    def evaluate_story_progression(self, chapter: int, character_name: str, user_choice: Dict) -> Dict:
        """评估故事进展和用户选择的影响，优化token使用"""
        try:
            # 获取交互ID
            interaction_id = user_choice.get('interaction_id', f"ch{chapter}_{int(time.time())}")
            
            # 获取当前角色的基本信息和交互状态
            current_state = self.interaction_state.get_chapter_state(chapter)
            
            # 获取当前章节摘要，而不是完整内容
            chapter_summary = self._get_chapter_summary(chapter)
            
            # 获取角色信息，只查当前章节的角色
            character_info = self.knowledge_base.get_character_context(character_name, chapter)
            
            # 检查是否有关联的交互点
            interaction_data = self.interaction_state.get_interaction_point_data(chapter, interaction_id)
            if not interaction_data:
                # 如果找不到交互点，可能是首次交互或ID丢失
                logger.warning(f"找不到交互点数据: chapter={chapter}, interaction_id={interaction_id}")
                
            # 定义评估结果模板，简化减少token使用
            progression_template = {
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
                "needs_correction": False
            }
            
            # 收集相关角色和事件，只获取必要的信息
            related_characters = {}
            if character_info and 'relationships' in character_info:
                for rel in character_info.get('relationships', [])[:3]:  # 只取前3个关系
                    target = rel.get('target', '')
                    if target and target in self.knowledge_base.characters:
                        related_info = self.knowledge_base.get_character_context(target, chapter)
                        if related_info:
                            # 简化角色信息，只保留描述和关系
                            related_characters[target] = {
                                "description": related_info.get('description', ''),
                                "relation_to_protagonist": rel.get('relation', '')
                            }
            
            # 获取相关事件，只获取当前章节的事件
            current_events = []
            for event in self.knowledge_base.events:
                if event.chapter == chapter:
                    # 只保留与当前角色相关的事件
                    if character_name in event.characters:
                        current_events.append({
                            "description": event.description,
                            "importance": event.importance,
                            "characters": event.characters[:3],  # 限制角色数量
                            "location": event.location
                        })
                    if len(current_events) >= 3:  # 最多保留3个事件
                        break
            
            # 构建评估提示，更简洁更针对性
            prompt = f"""评估用户在《小王子》互动小说中做出的选择，分析其对故事的影响。

### 基本信息
- 角色: {character_name}
- 章节: {chapter}
- 交互ID: {interaction_id}

### 角色信息
{json.dumps(character_info, ensure_ascii=False, indent=2) if character_info else "无角色信息"}

### 相关角色
{json.dumps(related_characters, ensure_ascii=False, indent=2)}

### 当前章节摘要
{chapter_summary}

### 当前事件
{json.dumps(current_events, ensure_ascii=False, indent=2)}

### 用户选择
{json.dumps(user_choice, ensure_ascii=False, indent=2)}

### 当前交互状态
- 进度: {current_state.get('progress', 0)}%
- 已有偏离: {json.dumps(current_state.get('divergences', [])[-2:] if len(current_state.get('divergences', [])) > 2 else current_state.get('divergences', []), ensure_ascii=False)}

请评估:

1. **故事进展**: 是否推动了故事发展？是否应进入下一章？
2. **情节偏离度**: 这个选择与原故事的偏离程度(0-5)，并说明关键变化。
3. **角色一致性**: 选择是否符合{character_name}的性格？是否促进角色发展？
4. **后续影响**: 预测2-3个可能的后续发展。
5. **是否需要修正**: 如果选择太过偏离，是否需要引导回主线？

评估结果必须是严格可解析的JSON格式:
{json.dumps(progression_template, ensure_ascii=False, indent=2)}"""

            # 调用LLM进行评估
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=1200
            )

            evaluation = handle_llm_response(lambda: response.choices[0].message.content)()
            
            # 更新交互状态
            if evaluation and interaction_id:
                # 更新交互点状态
                self.interaction_state.update_interaction_point(
                    chapter, 
                    interaction_id, 
                    {
                        "user_choice": user_choice.get('content', ''),
                        "evaluation": evaluation
                    }
                )
                
                # 如果存在偏离，记录到章节状态
                if 'divergence' in evaluation and evaluation['divergence'].get('level', 0) > 1:
                    self.interaction_state.add_story_divergence(
                        chapter, 
                        {
                            "level": evaluation['divergence'].get('level', 0),
                            "description": evaluation['divergence'].get('description', ''),
                            "key_changes": evaluation['divergence'].get('key_changes', []),
                            "interaction_id": interaction_id
                        }
                    )
                
                # 如果存在角色发展，记录到角色状态
                if 'character_impact' in evaluation and evaluation['character_impact'].get('development'):
                    self.interaction_state.update_character_development(
                        character_name,
                        {
                            "chapter": chapter,
                            "development": evaluation['character_impact'].get('development', []),
                            "interaction_id": interaction_id
                        }
                    )

            return evaluation
                
        except Exception as e:
            logger.error(f"评估故事进展时出错: {str(e)}")
            return {
                "should_proceed_chapter": False,
                "divergence": {"level": 0, "description": "无法评估", "key_changes": []},
                "character_impact": {"consistent": True, "development": []},
                "next_steps": ["继续当前章节"],
                "needs_correction": False
            }

class InteractionState:
    """用户交互状态管理类，专门负责跟踪用户交互"""
    
    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.state_file = settings.DATA_DIR / 'interactions' / f"{novel_id}_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 用户交互状态
        self.chapter_states = {}  # {chapter_num: {progress, choices, divergences}}
        self.interaction_history = {}  # {chapter_num: [interaction]}
        self.character_development = {}  # {character_name: [development]}
        self.interaction_ids = {}  # {chapter_num: {interaction_point_id: {status, choices}}}
        
        # 加载状态
        self.load_state()
    
    def load_state(self):
        """加载交互状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.chapter_states = state.get('chapter_states', {})
                    self.interaction_history = state.get('interaction_history', {})
                    self.character_development = state.get('character_development', {})
                    self.interaction_ids = state.get('interaction_ids', {})
            except Exception as e:
                logger.error(f"加载交互状态失败: {str(e)}")
    
    def save_state(self):
        """保存交互状态"""
        try:
            state = {
                'chapter_states': self.chapter_states,
                'interaction_history': self.interaction_history,
                'character_development': self.character_development,
                'interaction_ids': self.interaction_ids
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存交互状态失败: {str(e)}")
    
    def update_chapter_state(self, chapter: int, progress_info: Dict) -> None:
        """更新章节状态"""
        chapter_str = str(chapter)
        if chapter_str not in self.chapter_states:
            self.chapter_states[chapter_str] = {
                'progress': 0,
                'choices': [],
                'divergences': []
            }
        
        # 更新进度信息
        self.chapter_states[chapter_str].update(progress_info)
        self.save_state()
    
    def add_user_choice(self, chapter: int, choice: Dict) -> None:
        """添加用户选择"""
        chapter_str = str(chapter)
        if chapter_str not in self.chapter_states:
            self.chapter_states[chapter_str] = {
                'progress': 0,
                'choices': [],
                'divergences': []
            }
        
        # 添加用户选择
        self.chapter_states[chapter_str]['choices'].append({
            'timestamp': datetime.now().isoformat(),
            'choice_data': choice
        })
        self.save_state()
    
    def add_story_divergence(self, chapter: int, divergence: Dict) -> None:
        """添加故事偏离"""
        chapter_str = str(chapter)
        if chapter_str not in self.chapter_states:
            self.chapter_states[chapter_str] = {
                'progress': 0,
                'choices': [],
                'divergences': []
            }
        
        # 添加故事偏离
        self.chapter_states[chapter_str]['divergences'].append({
            'timestamp': datetime.now().isoformat(),
            'divergence_data': divergence
        })
        self.save_state()
    
    def update_character_development(self, character: str, development: Dict) -> None:
        """更新角色发展"""
        if character not in self.character_development:
            self.character_development[character] = []
        
        # 添加角色发展
        self.character_development[character].append({
            'timestamp': datetime.now().isoformat(),
            'development_data': development
        })
        self.save_state()
    
    def get_chapter_state(self, chapter: int) -> Dict:
        """获取章节状态"""
        chapter_str = str(chapter)
        return self.chapter_states.get(chapter_str, {
            'progress': 0,
            'choices': [],
            'divergences': []
        })
    
    def get_character_development(self, character: str) -> List[Dict]:
        """获取角色发展"""
        return self.character_development.get(character, [])
    
    def add_interaction_history(self, chapter: int, interaction: Dict) -> None:
        """添加交互历史"""
        chapter_str = str(chapter)
        if chapter_str not in self.interaction_history:
            self.interaction_history[chapter_str] = []
        
        # 添加交互历史
        self.interaction_history[chapter_str].append({
            'timestamp': datetime.now().isoformat(),
            'interaction_data': interaction
        })
        self.save_state()
    
    def get_chapter_interaction_history(self, chapter: int) -> List[Dict]:
        """获取章节交互历史"""
        chapter_str = str(chapter)
        return self.interaction_history.get(chapter_str, [])
    
    def get_last_interaction(self, chapter: int) -> Optional[Dict]:
        """获取最近的交互"""
        chapter_str = str(chapter)
        if chapter_str in self.interaction_history and self.interaction_history[chapter_str]:
            return self.interaction_history[chapter_str][-1]
        return None
        
    def register_interaction_point(self, chapter: int, interaction_id: str, options: List[Dict] = None) -> None:
        """注册交互点，跟踪章节内的多个交互点"""
        chapter_str = str(chapter)
        if chapter_str not in self.interaction_ids:
            self.interaction_ids[chapter_str] = {}
            
        self.interaction_ids[chapter_str][interaction_id] = {
            'status': 'pending',
            'options': options or [],
            'user_choice': None,
            'timestamp': datetime.now().isoformat()
        }
        self.save_state()
        
    def update_interaction_point(self, chapter: int, interaction_id: str, user_choice: Dict) -> None:
        """更新交互点状态"""
        chapter_str = str(chapter)
        if (chapter_str in self.interaction_ids and 
            interaction_id in self.interaction_ids[chapter_str]):
            
            self.interaction_ids[chapter_str][interaction_id].update({
                'status': 'completed',
                'user_choice': user_choice,
                'completion_time': datetime.now().isoformat()
            })
            self.save_state()
            
    def get_pending_interaction_points(self, chapter: int) -> List[str]:
        """获取章节中待处理的交互点"""
        chapter_str = str(chapter)
        if chapter_str not in self.interaction_ids:
            return []
            
        return [
            interaction_id for interaction_id, data in self.interaction_ids[chapter_str].items()
            if data['status'] == 'pending'
        ]
        
    def get_completed_interaction_points(self, chapter: int) -> List[str]:
        """获取章节中已完成的交互点"""
        chapter_str = str(chapter)
        if chapter_str not in self.interaction_ids:
            return []
            
        return [
            interaction_id for interaction_id, data in self.interaction_ids[chapter_str].items()
            if data['status'] == 'completed'
        ]
        
    def get_interaction_point_data(self, chapter: int, interaction_id: str) -> Optional[Dict]:
        """获取交互点数据"""
        chapter_str = str(chapter)
        if (chapter_str in self.interaction_ids and 
            interaction_id in self.interaction_ids[chapter_str]):
            
            return self.interaction_ids[chapter_str][interaction_id]
        return None