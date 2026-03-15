"""交互代理模块，负责用户与故事的交互处理

交互代理是用户与故事场景交互的核心组件，它整合了场景生成、用户输入评估、记忆管理和图像生成等功能。
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import json
import time
import os
from pathlib import Path
import re

from .scene_generator import SceneGenerator
from .input_evaluator import InputEvaluator
from .memory_manager import MemoryManager
from .image_generator import ImageGenerator
from .state_manager import StateManager

logger = logging.getLogger(__name__)

class InteractionAgent:
    """交互代理，负责用户与故事的交互处理"""
    
    def __init__(self, client, llm_model, config: Dict[str, Any] = None):
        """初始化交互代理
        
        Args:
            client: LLM客户端
            llm_model: 使用的语言模型
            config: 配置参数
        """
        self.client = client
        self.llm_model = llm_model
        self.config = config or {}
        self.document_language = self.config.get('document_language', 'chinese')
        
        # 初始化各个子模块
        self.scene_generator = SceneGenerator(client, llm_model, self.document_language)
        self.input_evaluator = InputEvaluator(client, llm_model, self.document_language)
        self.memory_manager = MemoryManager()
        
        # 图像生成服务可能需要外部API
        image_service = self.config.get('image_service')
        self.image_generator = ImageGenerator(client, llm_model, self.document_language, image_service)
        
        # 语音服务
        self.voice_service = None
        if self.config.get('voice_app_id'):
            try:
                from agent.services.voice_service import VoiceService
                logger.info(f"正在初始化语音服务，app_id={self.config.get('voice_app_id')[:5]}***")
                logger.info(f"[DEBUG][InteractionAgent.__init__] voice_app_id={self.config.get('voice_app_id')[:5]}***, voice_token={'YES' if self.config.get('voice_token') else 'NO'}")
                self.voice_service = VoiceService(
                    app_id=self.config.get('voice_app_id'),
                    token=self.config.get('voice_token'),
                    llm_client=client,
                    llm_model=llm_model
                )
                logger.info("语音服务初始化成功")
            except ImportError:
                logger.warning("无法导入VoiceService，语音功能将不可用")
        else:
            logger.warning("未配置voice_app_id，语音功能将不可用")
            logger.info(f"[DEBUG][InteractionAgent.__init__] 配置中无voice_app_id, config={self.config}")
        
        # 状态管理
        data_dir = self.config.get('data_dir', './data')
        self.state_manager = StateManager(data_dir)
        
        # 交互状态
        self.document_id = None
        self.character_name = None
        self.current_chapter = 1
        self.character_info = None
        self.chapter_summary = None
        self.chapter_events = None
        self.current_scene = None
    
    def set_interaction_context(self, document_id: str, character_name: str, 
                               character_info: Dict[str, Any], chapter: int,
                               chapter_summary: Dict[str, Any] = None,
                               chapter_events: List[Dict[str, Any]] = None) -> None:
        """设置交互上下文
        
        Args:
            document_id: 文档ID
            character_name: 角色名称
            character_info: 角色信息
            chapter: 章节
            chapter_summary: 章节摘要
            chapter_events: 章节事件
        """
        self.document_id = document_id
        self.character_name = character_name
        self.current_chapter = chapter
        self.character_info = character_info
        self.chapter_summary = chapter_summary
        self.chapter_events = chapter_events
        
        # 根据文档ID确定语言
        if document_id.startswith('en-'):
            self.document_language = 'english'
        
        # 设置状态管理器上下文
        self.state_manager.set_interaction_context(document_id, character_name, chapter)
        
        # 检查记忆库是否为空，如果为空则生成初始元数据
        if len(self.memory_manager.memory_store) == 0:
            self.generate_initial_metadata(document_id)
        
        # 日志记录
        logger.info(f"已设置交互上下文: 文档={document_id}, 角色={character_name}, 章节={chapter}")
    
    def start_interaction(self) -> Dict[str, Any]:
        """开始交互
        
        Returns:
            Dict[str, Any]: 初始场景
        """
        # 检查上下文是否已设置
        if not (self.document_id and self.character_name and self.current_chapter):
            logger.error("未设置交互上下文，无法开始交互")
            raise ValueError("未设置交互上下文")
        
        # 检查是否有之前的场景，如果有则直接返回
        last_scene = self.state_manager.get_last_scene()
        if last_scene:
            self.current_scene = last_scene
            logger.info(f"返回之前的场景：{last_scene.get('interaction_id', 'unknown')}")
            return last_scene
        
        # 生成初始场景
        cross_chapter_memory = self.memory_manager.get_cross_chapter_memory()
        
        scene = self.scene_generator.generate_scene(
            character_name=self.character_name,
            current_chapter=self.current_chapter,
            character_info=self.character_info,
            chapter_summary=self.chapter_summary,
            chapter_events=self.chapter_events,
            cross_chapter_memory=cross_chapter_memory
        )
        
        # 更新记忆
        self.memory_manager.update_memory_store(scene, self.character_name, self.current_chapter)
        
        # 保存场景到历史
        self.state_manager.add_scene_to_history(scene)
        
        # 更新当前场景
        self.current_scene = scene
        
        return scene
    
    def process_user_input(self, user_input: str, auto_generate_image: bool = False, 
                          image_config: Dict[str, Any] = None, 
                          accept_deviation: bool = False) -> Dict[str, Any]:
        """处理用户输入
        
        Args:
            user_input: 用户输入
            auto_generate_image: 是否自动生成图像
            image_config: 图像配置
            accept_deviation: 是否接受故事偏离，用于用户确认继续偏离主线的情况
            
        Returns:
            Dict[str, Any]: 处理结果，包含新场景或错误信息
        """
        if not user_input or not user_input.strip():
            return {
                "status": "error",
                "message": "用户输入不能为空"
            }
            
        # 检查是否有当前场景
        if not self.current_scene:
            return {
                "status": "error",
                "message": "无当前场景，请先开始交互"
            }
            
        # 获取相关记忆
        related_memories = self.memory_manager.get_related_memories(user_input)
        
        # 获取当前进度、最近选择和偏离
        current_progress = self.state_manager.get_current_progress()
        recent_choices = self.state_manager.get_recent_choices()
        recent_divergences = self.state_manager.get_recent_divergences()
        
        try:
            # 如果用户已经确认接受偏离，直接生成偏离结局
            if accept_deviation:
                logger.info(f"用户选择继续偏离主线的故事: {user_input}")
                last_divergence = recent_divergences[-1] if recent_divergences else None
                
                # 生成偏离结局场景
                deviation_scene = self.scene_generator.generate_deviation_scene(
                    character_name=self.character_name,
                    current_chapter=self.current_chapter,
                    user_input=user_input,
                    last_scene=self.current_scene,
                    character_info=self.character_info,
                    chapter_summary=self.chapter_summary,
                    last_divergence=last_divergence,
                    cross_chapter_memory=self.memory_manager.get_cross_chapter_memory()
                )
                
                # 添加偏离结局到历史
                self.state_manager.add_deviated_ending_to_history(deviation_scene)
                
                # 更新当前场景
                self.current_scene = deviation_scene
                
                # 自动生成图像（如果开启）
                image_result = None
                if auto_generate_image and image_config:
                    image_result = self.image_generator.auto_generate_image(
                        scene=deviation_scene,
                        access_key_id=image_config.get('access_key_id'),
                        secret_key=image_config.get('secret_key'),
                        base_url=image_config.get('base_url')
                    )
                
                # 返回偏离结局场景和可能的图像
                result = {
                    "status": "deviated_ending",
                    "scene": deviation_scene,
                    "image_result": image_result,
                    "message": "已生成偏离主线结局"
                }
                
                # 添加图像URL（如果有）
                if image_result and image_result.get('status') == 'success':
                    if 'image_url' in image_result:
                        result['image_url'] = image_result['image_url']
                    if 'remote_url' in image_result:
                        result['remote_url'] = image_result['remote_url']
                    
                return result
    
            # 评估用户输入
            evaluation = self.input_evaluator.evaluate_user_input(
                user_input=user_input,
                last_scene=self.current_scene,
                character_name=self.character_name,
                current_chapter=self.current_chapter,
                character_info=self.character_info,
                chapter_summary=self.chapter_summary,
                chapter_events=self.chapter_events,
                related_memories=related_memories,
                current_progress=current_progress,
                recent_divergences=recent_divergences
            )
            
            # 添加用户输入和评估结果到历史
            self.state_manager.add_user_input_to_history(user_input, evaluation)
            
            # 检查是否需要切换章节
            if evaluation.get('should_proceed_chapter', False):
                new_chapter = self.current_chapter + 1
                # 生成本章摘要并添加到记忆
                scenes = self.state_manager.get_scenes_in_history()
                self.memory_manager.generate_chapter_summary(
                    scenes, self.current_chapter, self.character_name, self.client, self.llm_model
                )
                
                # 过渡到新章节
                self.transition_to_new_chapter(new_chapter)
                
                # 返回特殊标记，表示需要切换章节
                return {
                    "status": "chapter_transition",
                    "message": f"准备进入第{new_chapter}章",
                    "new_chapter": new_chapter
                }
            
            # 检查是否需要处理偏离剧情
            divergence = evaluation.get('divergence', {})
            divergence_level = divergence.get('level', 0)
            needs_correction = evaluation.get('needs_correction', False)
            
            # 如果偏离度高(≥4)且需要修正，提示用户是否继续
            # 将触发警告的阈值从3提高到4，只对较严重的偏离显示警告
            if divergence_level >= 4 and needs_correction:
                # 添加偏离记录
                if recent_divergences and len(recent_divergences) > 0:
                    # 只有当最近没有相同的偏离时才添加
                    if recent_divergences[-1].get('description') != divergence.get('description'):
                        self.state_manager.current_state['divergences'].append({
                            'timestamp': time.time(),
                            'description': divergence.get('description', ''),
                            'level': divergence_level
                        })
                else:
                    self.state_manager.current_state['divergences'].append({
                        'timestamp': time.time(),
                        'description': divergence.get('description', ''),
                        'level': divergence_level
                    })
                    
                # 保存当前状态
                self.state_manager.save_interaction_state()
                
                # 返回警告信息
                return {
                    "status": "warning",
                    "message": "检测到故事偏离主线",
                    "divergence": divergence,
                    "original_input": user_input
                }
            
            # 正常继续生成场景
            cross_chapter_memory = self.memory_manager.get_cross_chapter_memory()
            
            # 生成新场景
            scene = self.scene_generator.generate_scene(
                character_name=self.character_name,
                current_chapter=self.current_chapter,
                character_info=self.character_info,
                chapter_summary=self.chapter_summary,
                chapter_events=self.chapter_events,
                cross_chapter_memory=cross_chapter_memory,
                user_input=user_input,
                evaluation=evaluation,
                current_progress=evaluation.get('progress', current_progress),
                recent_choices=recent_choices,
                recent_divergences=recent_divergences
            )
            
            # 更新记忆
            self.memory_manager.update_memory_store(scene, self.character_name, self.current_chapter)
            
            # 保存场景到历史
            self.state_manager.add_scene_to_history(scene)
            
            # 更新当前场景
            self.current_scene = scene
            
            # 自动生成图像（如果开启）
            image_result = None
            if auto_generate_image and image_config:
                image_result = self.image_generator.auto_generate_image(
                    scene=scene,
                    access_key_id=image_config.get('access_key_id'),
                    secret_key=image_config.get('secret_key'),
                    base_url=image_config.get('base_url')
                )
            
            # 返回新场景和可能的图像
            result = {
                "status": "success",
                "scene": scene,
                "image_result": image_result,
                "should_proceed_chapter": evaluation.get('should_proceed_chapter', False)
            }
            
            # 添加图像URL（如果有）
            if image_result and image_result.get('status') == 'success':
                if 'image_url' in image_result:
                    result['image_url'] = image_result['image_url']
                if 'remote_url' in image_result:
                    result['remote_url'] = image_result['remote_url']
                    
            return result
            
        except Exception as e:
            logger.exception(f"处理用户输入失败: {str(e)}")
            return {
                "status": "error",
                "message": f"处理失败: {str(e)}"
            }
    
    def generate_image_for_scene(self, scene_id: str = None, 
                                style: str = None, 
                                image_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """为场景生成图像
        
        Args:
            scene_id: 场景ID，默认为当前场景
            style: 图像风格
            image_config: 图像配置
            
        Returns:
            Dict[str, Any]: 图像生成结果
        """
        if not image_config:
            return {
                "status": "error",
                "message": "未提供图像生成配置"
            }
            
        # 确定要生成图像的场景
        target_scene = None
        if scene_id:
            # 从历史记录中查找指定场景
            scenes = self.state_manager.get_scenes_in_history()
            for scene in scenes:
                if scene.get('interaction_id') == scene_id:
                    target_scene = scene
                    break
        else:
            # 使用当前场景
            target_scene = self.current_scene
            
        if not target_scene:
            return {
                "status": "error",
                "message": "未找到指定场景"
            }
            
        # 确定图像风格
        if not style:
            style = self.image_generator.determine_image_style(target_scene)
            
        # 生成图像
        return self.image_generator.generate_image_from_scene(
            scene=target_scene,
            access_key_id=image_config.get('access_key_id'),
            secret_key=image_config.get('secret_key'),
            base_url=image_config.get('base_url'),
            style=style
        )
    
    def transition_to_new_chapter(self, new_chapter: int, 
                                chapter_summary: Dict[str, Any] = None,
                                chapter_events: List[Dict[str, Any]] = None) -> None:
        """过渡到新章节
        
        Args:
            new_chapter: 新章节编号
            chapter_summary: 新章节摘要
            chapter_events: 新章节事件
        """
        # 更新章节信息
        self.current_chapter = new_chapter
        if chapter_summary:
            self.chapter_summary = chapter_summary
        if chapter_events:
            self.chapter_events = chapter_events
            
        # 更新状态管理器
        self.state_manager.transition_to_new_chapter(new_chapter)
    
    def load_memories(self, memory_data: List[Dict[str, Any]]) -> None:
        """加载记忆数据
        
        Args:
            memory_data: 记忆数据
        """
        self.memory_manager.load_memories(memory_data)
    
    def get_interaction_history(self) -> List[Dict[str, Any]]:
        """获取交互历史
        
        Returns:
            List[Dict[str, Any]]: 交互历史
        """
        return self.state_manager.interaction_history

    def generate_initial_metadata(self, document_id: str) -> Dict[str, Any]:
        """生成并添加故事元数据和时间线
        
        该方法会生成包括世界观、风格、时间线、人物特点和主题的元数据，
        为交互提供更好的上下文信息。
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 生成的元数据
        """
        logger.info(f"为文档 {document_id} 生成初始元数据")
        
        try:
            # 构建提示
            is_english = self.document_language == 'english'
            
            # 获取跨章节记忆
            cross_chapter_memory = self.memory_manager.get_cross_chapter_memory()
            
            # 获取角色信息
            character_info = self.character_info or {}
            
            # 获取章节摘要和事件
            chapter_summary = self.chapter_summary or {}
            chapter_events = self.chapter_events or []
            
            # 创建英文或中文提示
            if is_english:
                prompt = f"""As a literary analysis expert, create comprehensive metadata for this novel to enhance immersive reading. This metadata will provide context for the interactive storytelling experience.

## Basic Information
- Document ID: {document_id}
- Character: {self.character_name}
- Chapter: {self.current_chapter}

## Available Context
{json.dumps(character_info, ensure_ascii=False, indent=2) if character_info else "No character information available"}

{json.dumps(chapter_summary, ensure_ascii=False, indent=2) if chapter_summary else "No chapter summary available"}

{json.dumps(chapter_events, ensure_ascii=False, indent=2) if chapter_events else "No chapter events available"}

{json.dumps(cross_chapter_memory, ensure_ascii=False, indent=2) if cross_chapter_memory else "No cross-chapter memory available"}

Please create a rich, informative summary (500-1000 words) including:

1. Timeline: Key events and their chronological order in the story
2. World-building: Setting, historical context, and unique features of the story world
3. Writing style: Literary techniques, narrative voice, and stylistic elements
4. Character development: Psychological depth and growth patterns of main characters
5. Themes: Core ideas and philosophical elements explored in the text
6. Motifs: Recurring images, concepts, or symbols

Format your answer as a JSON object with the following structure:
{{
  "timeline": "Brief timeline of main events",
  "world_building": "Description of the setting and world",
  "style": "Analysis of writing style and narrative techniques",
  "character_development": "Overview of character arcs and psychological elements",
  "themes": "Main themes and philosophical ideas",
  "motifs": "Recurring symbols and imagery"
}}

This metadata will help generate more consistent and contextually appropriate responses during interactive storytelling."""
            else:
                prompt = f"""作为文学分析专家，请为这部小说创建一个全面的元数据摘要。这个摘要将用于增强沉浸式阅读体验，为交互式讲故事提供上下文信息。

## 基本信息
- 文档ID: {document_id}
- 角色: {self.character_name}
- 章节: {self.current_chapter}

## 可用上下文
{json.dumps(character_info, ensure_ascii=False, indent=2) if character_info else "无角色信息"}

{json.dumps(chapter_summary, ensure_ascii=False, indent=2) if chapter_summary else "无章节摘要"}

{json.dumps(chapter_events, ensure_ascii=False, indent=2) if chapter_events else "无章节事件"}

{json.dumps(cross_chapter_memory, ensure_ascii=False, indent=2) if cross_chapter_memory else "无跨章节记忆"}

请创建一个内容丰富、信息全面的摘要（500-1000字），包括以下内容：

1. 时间线：故事中的关键事件和时间顺序
2. 世界观：故事的背景设定、时代背景以及故事世界的独特特征
3. 写作风格：文学技巧、叙事声音和风格元素
4. 人物塑造：主要角色的心理深度和成长模式
5. 主题：文本中探讨的核心思想和哲学元素
6. 意象：反复出现的图像、概念或符号

请将您的回答格式化为JSON对象，结构如下：
{{
  "timeline": "主要事件的简要时间线",
  "world_building": "小说的背景设定和世界描述",
  "style": "写作风格和叙事技巧分析",
  "character_development": "角色弧线和心理元素概述",
  "themes": "主要主题和哲学思想",
  "motifs": "反复出现的符号和意象"
}}

这些元数据将帮助在交互式讲故事过程中生成更一致和更符合上下文的回应。"""
            
            # 调用LLM生成元数据
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
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
                    
                metadata = json.loads(content)
                
                # 添加到记忆库
                if metadata.get('timeline'):
                    self.memory_manager.memory_store.append({
                        'content': f"故事时间线：{metadata['timeline']}",
                        'chapter': 0,  # 表示这是全局信息
                        'character': self.character_name,
                        'timestamp': time.time(),
                        'importance': 5,  # 最高重要性
                        'type': 'metadata_timeline'
                    })
                    
                if metadata.get('world_building'):
                    self.memory_manager.memory_store.append({
                        'content': f"世界背景：{metadata['world_building']}",
                        'chapter': 0,
                        'character': self.character_name,
                        'timestamp': time.time(),
                        'importance': 5,
                        'type': 'metadata_world'
                    })
                    
                if metadata.get('character_development'):
                    self.memory_manager.memory_store.append({
                        'content': f"人物塑造：{metadata['character_development']}",
                        'chapter': 0,
                        'character': self.character_name,
                        'timestamp': time.time(),
                        'importance': 4.5,
                        'type': 'metadata_characters'
                    })
                    
                if metadata.get('themes'):
                    self.memory_manager.memory_store.append({
                        'content': f"主题思想：{metadata['themes']}",
                        'chapter': 0,
                        'character': self.character_name,
                        'timestamp': time.time(),
                        'importance': 4,
                        'type': 'metadata_themes'
                    })
                    
                logger.info(f"成功生成元数据，并添加到记忆库")
                return metadata
                
            except json.JSONDecodeError:
                logger.warning("LLM返回的内容不是有效的JSON格式")
                # 尝试查找JSON内容
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, content)
                
                if match:
                    try:
                        metadata = json.loads(match.group(0))
                        return metadata
                    except:
                        logger.error("无法解析提取的JSON内容")
                    
            # 如果生成失败，返回空字典
            return {}
            
        except Exception as e:
            logger.exception(f"生成元数据失败: {str(e)}")
            return {}

    def generate_audio_for_scene(self, scene: Dict[str, Any] = None, scene_id: str = None) -> Dict[str, Any]:
        logger.info(f"[DEBUG] 调用了generate_audio_for_scene, scene参数类型: {type(scene)}, scene_id: {scene_id}")
        """为场景生成语音
        
        Args:
            scene: 场景对象，优先使用
            scene_id: 场景ID，默认为当前场景
            
        Returns:
            Dict[str, Any]: 语音生成结果
        """
        if not self.voice_service:
            logger.error("语音服务未初始化，请先设置voice_app_id和voice_token")
            return {
                "status": "error",
                "message": "语音服务未初始化"
            }
        
        # 确保语音服务有LLM客户端
        if not self.voice_service.llm_client and self.client:
            logger.info("设置语音服务的LLM客户端")
            self.voice_service.set_llm_client(self.client, self.llm_model)
            
        # 优先使用scene参数
        target_scene = None
        if scene is not None:
            target_scene = scene
        elif scene_id:
            # 从历史记录中查找指定场景
            scenes = self.state_manager.get_scenes_in_history()
            for s in scenes:
                if s.get('interaction_id') == scene_id:
                    target_scene = s
                    break
        else:
            # 使用当前场景
            target_scene = self.current_scene
        
        if not target_scene:
            logger.warning("未找到指定场景，无法生成语音")
            return {
                "status": "error",
                "message": "未找到指定场景"
            }
        
        # 记录详细信息
        narrative = target_scene.get('narrative', '')
        logger.info(f"为场景生成语音，场景ID: {target_scene.get('interaction_id', 'unknown')}, 文本长度: {len(narrative)}")
        logger.info(f"场景内容前100字: {narrative[:100]}")
        
        # 强制发起DeepSeek调用以提取对话
        try:
            # 确保使用LLM提取对话
            logger.info("---------- 开始使用DeepSeek提取对话 ----------")
            if not self.voice_service.llm_client:
                logger.info("语音服务没有LLM客户端，尝试设置")
                self.voice_service.set_llm_client(self.client, self.llm_model)
            
            # 直接调用LLM对话提取方法
            dialogues = self.voice_service._extract_dialogues_with_llm(narrative)
            logger.info(f"DeepSeek成功提取到 {len(dialogues)} 段对话")
            
            # 记录提取到的对话
            for i, dialog in enumerate(dialogues[:3]):  # 只显示前3段对话用于调试
                logger.info(f"对话{i+1}: [{dialog.get('speaker', '')}] {dialog.get('content', '')[:30]}...")
            
            # 正常调用语音生成流程
            logger.info("调用语音服务生成音频...")
            result = self.voice_service.generate_audio_for_scene(target_scene)
            logger.info(f"语音生成完成: {result.get('status')}")
            
            return result
        except Exception as e:
            logger.exception(f"使用DeepSeek提取对话失败: {str(e)}")
            
            # 如果LLM提取失败，回退到普通语音生成
            logger.info("回退到普通语音生成...")
            try:
                result = self.voice_service.generate_audio_for_scene(target_scene)
                return result
            except Exception as e2:
                logger.exception(f"生成场景语音失败: {str(e2)}")
                return {
                    "status": "error",
                    "message": f"生成场景语音失败: {str(e2)}"
                }

    def set_voice_app_id(self, app_id: str, token: str = None) -> Dict[str, Any]:
        """设置语音服务AppID和Token
        
        Args:
            app_id: 火山引擎语音合成AppID
            token: 火山引擎语音合成Token
            
        Returns:
            Dict[str, Any]: 设置结果
        """
        result = {
            "status": "error",
            "message": "未知错误"
        }
        
        if not app_id:
            result["message"] = "AppID不能为空"
            return result
            
        try:
            # 如果已有语音服务实例，则直接更新
            if self.voice_service:
                logger.info(f"更新现有语音服务: app_id={app_id[:5] if app_id else None}***")
                self.voice_service.set_app_id(app_id)
                if token:
                    self.voice_service.set_token(token)
                
                # 更新配置
                self.config['voice_app_id'] = app_id
                if token:
                    self.config['voice_token'] = token
                
                result["status"] = "success"
                result["message"] = "语音服务配置已更新"
                return result
            
            # 创建新的语音服务实例
            try:
                from agent.services.voice_service import VoiceService
                logger.info(f"创建新的语音服务: app_id={app_id[:5] if app_id else None}***")
                
                self.voice_service = VoiceService(
                    app_id=app_id,
                    token=token,
                    llm_client=self.client,
                    llm_model=self.llm_model
                )
                
                # 更新配置
                self.config['voice_app_id'] = app_id
                if token:
                    self.config['voice_token'] = token
                
                logger.info("语音服务初始化成功")
                result["status"] = "success"
                result["message"] = "语音服务初始化成功"
                return result
            except ImportError:
                logger.warning("无法导入VoiceService，语音功能将不可用")
                result["message"] = "无法导入VoiceService，语音功能将不可用"
                return result
        except Exception as e:
            logger.exception(f"设置语音服务AppID时出错: {str(e)}")
            result["message"] = f"设置语音服务AppID时出错: {str(e)}"
            return result