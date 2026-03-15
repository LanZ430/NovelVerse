"""交互代理适配器模块，提供与原有接口兼容的适配器

该模块确保重构后的交互代理能够与原有代码无缝集成，保持接口兼容性。
"""

from typing import Dict, Any, List, Optional
import logging
import os
from pathlib import Path
import time
import json
from openai import OpenAI

from agent.core.base_agent import BaseAgent
from .interaction_agent import InteractionAgent
from .scene_generator import SceneGenerator
from .input_evaluator import InputEvaluator
from .memory_manager import MemoryManager
from .image_generator import ImageGenerator
from .state_manager import StateManager

logger = logging.getLogger(__name__)

class InteractionAgentAdapter(BaseAgent):
    """交互代理适配器，提供与原有接口兼容的适配层"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化交互代理适配器
        
        Args:
            config: 配置信息，包括：
                - data_dir: 数据存储目录
                - llm_api_key: 大语言模型API密钥
                - llm_base_url: 大语言模型API基础URL
                - llm_model: 大语言模型名称
                - voice_app_id: 火山引擎语音合成AppID
        """
        super().__init__(config)
        
        # 设置LLM客户端
        llm_api_key = self.config.get('llm_api_key')
        llm_base_url = self.config.get('llm_base_url', 'https://api.deepseek.com')
        self.client = OpenAI(
            api_key=llm_api_key,
            base_url=llm_base_url
        )
        self.llm_model = self.config.get('llm_model', 'deepseek-chat')
        
        # 创建实际的交互代理实例
        self.interaction_agent = InteractionAgent(
            client=self.client,
            llm_model=self.llm_model,
            config=self.config
        )
        
        # 知识库和角色信息
        self.knowledge_base = {}
        self.characters = {}
        self.settings = {}
        self.plots = []
        self.chapter_summaries = []
        
        # 文档语言，默认中文
        self.document_language = 'chinese'
    
    def initialize(self) -> bool:
        """初始化交互代理资源
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 创建必要的目录
            data_dir = self.config.get('data_dir', './data')
            interactions_dir = Path(data_dir) / 'interactions'
            interactions_dir.mkdir(parents=True, exist_ok=True)
            
            self.is_initialized = True
            logger.info("交互代理初始化成功")
            return True
        except Exception as e:
            logger.exception(f"交互代理初始化失败: {str(e)}")
            return False
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行交互代理，根据交互类型分发到不同处理方法
        
        Args:
            context: 上下文信息，包括：
                - action: 交互类型，支持：
                    - start: 开始新交互
                    - continue: 继续交互
                    - stop: 停止交互
                    - next_chapter: 进入下一章节
                    - jump_to: 跳转到指定章节
                    - search_info: 搜索相关信息
                - document_id: 文档ID
                - character_name: 角色名称
                - chapter: 章节编号
                - user_input: 用户输入
                - knowledge_base: 知识库
                - query: 搜索查询
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        super().execute(context)
        
        action = context.get('action')
        
        if action == 'start':
            return self._start_interaction(context)
        elif action == 'continue':
            return self._continue_interaction(context)
        elif action == 'stop':
            return self._stop_interaction(context)
        elif action == 'next_chapter':
            return self._next_chapter(context)
        elif action == 'jump_to':
            return self._jump_to_chapter(context)
        elif action == 'search_info':
            return self._search_story_info(context)
        else:
            logger.error(f"不支持的交互类型: {action}")
            return {
                "status": "error",
                "message": f"不支持的交互类型: {action}"
            }
    
    def _start_interaction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """开始新的交互
        
        Args:
            context: 上下文信息
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 获取必要参数
        document_id = context.get('document_id')
        character_name = context.get('character_name')
        chapter = context.get('chapter', 1)
        knowledge_base = context.get('knowledge_base')
        
        # 获取图像API配置
        access_key_id = context.get('access_key_id')
        secret_key = context.get('secret_key')
        base_url = context.get('base_url')
        auto_image = context.get('auto_image', True)  # 默认开启自动生成图像
        
        # 获取语音API配置
        voice_app_id = context.get('voice_app_id') or self.config.get('voice_app_id')
        voice_token = context.get('voice_token') or self.config.get('voice_token')
        auto_voice = context.get('auto_voice', True)  # 默认开启自动生成语音
        
        if not document_id:
            return {
                "status": "error",
                "message": "文档ID不能为空"
            }
            
        if not character_name:
            return {
                "status": "error",
                "message": "角色名称不能为空"
            }
        
        # 加载知识库
        if knowledge_base:
            self.knowledge_base = knowledge_base
            self.characters = knowledge_base.get('characters', {})
            self.settings = knowledge_base.get('settings', {})
            self.plots = knowledge_base.get('plots', [])
            self.chapter_summaries = knowledge_base.get('chapter_summaries', [])
        
        # 获取角色信息
        character_info = self._get_character_info(character_name)
        
        # 获取章节摘要
        chapter_summary = self._get_chapter_summary(chapter)
        
        # 获取章节事件
        chapter_events = self._get_chapter_events(chapter)
        
        # 设置交互上下文
        self.interaction_agent.set_interaction_context(
            document_id=document_id, 
            character_name=character_name,
            character_info=character_info,
            chapter=chapter,
            chapter_summary=chapter_summary,
            chapter_events=chapter_events
        )
        
        # 开始交互，获取初始场景
        scene = self.interaction_agent.start_interaction()
        
        # 自动生成图像（如果配置了）
        image_url = None
        remote_url = None
        if auto_image and access_key_id and secret_key:
            image_config = {
                'access_key_id': access_key_id,
                'secret_key': secret_key,
                'base_url': base_url
            }
            
            try:
                image_result = self.interaction_agent.generate_image_for_scene(
                    scene_id=None,  # 使用当前场景
                    style=None,  # 自动确定风格
                    image_config=image_config
                )
                
                # 提取图像URL
                if image_result and image_result.get('status') == 'success':
                    image_url = image_result.get('image_url')
                    remote_url = image_result.get('remote_url')
            except Exception as e:
                logger.warning(f"自动生成图像失败: {str(e)}")
        
        # 自动生成语音（如果配置了）
        audio_result = None
        logger.info(f"[DEBUG] auto_voice={auto_voice}, voice_app_id={voice_app_id}, voice_token={'YES' if voice_token else 'NO'}")
        logger.info(f"[DEBUG] adapter配置中的语音设置: voice_app_id={self.config.get('voice_app_id')}, voice_token={'YES' if self.config.get('voice_token') else 'NO'}")
        if auto_voice and voice_app_id and voice_token:
            logger.info("[DEBUG] 进入自动生成语音分支 (_start_interaction)")
            try:
                # 确保语音服务初始化
                if not self.interaction_agent.voice_service:
                    logger.info("[DEBUG] 语音服务未初始化，尝试初始化")
                    try:
                        from agent.services.voice_service import VoiceService
                        self.interaction_agent.voice_service = VoiceService(
                            app_id=voice_app_id,
                            token=voice_token,
                            llm_client=self.client,
                            llm_model=self.llm_model
                        )
                        logger.info(f"[DEBUG] 实时初始化语音服务结果: {self.interaction_agent.voice_service is not None}")
                    except Exception as e:
                        logger.exception(f"[DEBUG] 实时初始化语音服务失败: {str(e)}")
                
                logger.info("开始自动生成语音...")
                # 传递当前场景对象scene
                audio_result = self.interaction_agent.generate_audio_for_scene(scene)
                
                # 记录详细的结果信息
                if audio_result:
                    logger.info(f"语音生成结果: {audio_result.get('status')}, 对话数量: {len(audio_result.get('dialogues', []))}")
                    if audio_result.get('status') != 'success':
                        logger.warning(f"语音生成未成功: {audio_result.get('message', '未知错误')}")
                else:
                    logger.warning("语音生成返回空结果")
            except Exception as e:
                logger.exception(f"自动生成语音失败: {str(e)}")
        
        # 返回结果
        result = {
            "status": "success",
            "scene": scene,
            "character_name": character_name,
            "chapter": chapter,
            "document_id": document_id
        }
        
        # 添加图像URL（如果有）
        if image_url:
            result["image_url"] = image_url
        if remote_url:
            result["remote_url"] = remote_url
        
        # 添加语音结果（如果有）
        if audio_result and audio_result.get('status') == 'success':
            result["audio_result"] = audio_result
        
        return result
    
    def _continue_interaction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """继续交互
        
        Args:
            context: 上下文信息
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 获取必要参数
        user_input = context.get('user_input')
        document_id = context.get('document_id')
        character_name = context.get('character_name')
        force_continue = context.get('force_continue', False)  # 添加force_continue参数的处理
        
        # 图像生成配置
        access_key_id = context.get('access_key_id')
        secret_key = context.get('secret_key')
        base_url = context.get('base_url')
        auto_image = context.get('auto_image', True)
        
        # 语音生成配置
        voice_app_id = context.get('voice_app_id') or self.config.get('voice_app_id')
        voice_token = context.get('voice_token') or self.config.get('voice_token')
        auto_voice = context.get('auto_voice', True)
        
        if not user_input:
            return {
                "status": "error",
                "message": "用户输入不能为空"
            }
            
        # 如果未设置文档ID和角色名称，尝试从interaction_agent中获取
        if not document_id:
            document_id = self.interaction_agent.document_id
        if not character_name:
            character_name = self.interaction_agent.character_name
            
        # 准备图像配置
        image_config = None
        if auto_image and access_key_id and secret_key:
            image_config = {
                'access_key_id': access_key_id,
                'secret_key': secret_key,
                'base_url': base_url
            }
            
        # 处理用户输入，如果force_continue为True，则设置accept_deviation为True
        result = self.interaction_agent.process_user_input(
            user_input=user_input,
            auto_generate_image=auto_image,
            image_config=image_config,
            accept_deviation=force_continue  # 使用force_continue作为accept_deviation参数
        )
        
        # 添加角色和章节信息
        if result.get('status') == 'success' or result.get('status') == 'deviated_ending':
            result['character_name'] = character_name
            result['chapter'] = self.interaction_agent.current_chapter
            result['document_id'] = document_id
            
            # 确保图像URL被正确传递
            # 从内部image_result字段中提取图像URL
            image_result = result.get('image_result', {})
            if image_result:
                if 'image_url' in image_result and image_result['image_url']:
                    result['image_url'] = image_result['image_url']
                if 'remote_url' in image_result and image_result['remote_url']:
                    result['remote_url'] = image_result['remote_url']
            
            # 自动生成语音（如果配置了）
            audio_result = None
            logger.info(f"[DEBUG] auto_voice={auto_voice}, voice_app_id={voice_app_id}, voice_token={'YES' if voice_token else 'NO'}")
            logger.info(f"[DEBUG] adapter配置中的语音设置: voice_app_id={self.config.get('voice_app_id')}, voice_token={'YES' if self.config.get('voice_token') else 'NO'}")
            if auto_voice and voice_app_id and voice_token:
                logger.info("[DEBUG] 进入自动生成语音分支 (_continue_interaction)")
                try:
                    # 确保语音服务初始化
                    if not self.interaction_agent.voice_service:
                        logger.info("[DEBUG] 语音服务未初始化，尝试初始化")
                        try:
                            from agent.services.voice_service import VoiceService
                            self.interaction_agent.voice_service = VoiceService(
                                app_id=voice_app_id,
                                token=voice_token,
                                llm_client=self.client,
                                llm_model=self.llm_model
                            )
                            logger.info(f"[DEBUG] 实时初始化语音服务结果: {self.interaction_agent.voice_service is not None}")
                        except Exception as e:
                            logger.exception(f"[DEBUG] 实时初始化语音服务失败: {str(e)}")
                    
                    logger.info("继续交互 - 开始自动生成语音...")
                    # 获取当前场景
                    current_scene = result.get('scene')
                    if current_scene:
                        # 传递当前场景对象
                        audio_result = self.interaction_agent.generate_audio_for_scene(current_scene)
                        # 记录详细的结果信息
                        if audio_result:
                            logger.info(f"语音生成结果: {audio_result.get('status')}, 对话数量: {len(audio_result.get('dialogues', []))}")
                            if audio_result.get('status') != 'success':
                                logger.warning(f"语音生成未成功: {audio_result.get('message', '未知错误')}")
                            if audio_result.get('status') == 'success':
                                result["audio_result"] = audio_result
                        else:
                            logger.warning("语音生成返回空结果")
                except Exception as e:
                    logger.exception(f"自动生成语音失败: {str(e)}")
        
        return result
    
    def _stop_interaction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """停止交互
        
        Args:
            context: 上下文信息
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 目前interaction_agent不直接支持停止，但可以通过将状态保存实现
        # 在此处简单返回成功
        return {
            "status": "success",
            "message": "交互已停止"
        }
    
    def _next_chapter(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """进入下一章节
        
        Args:
            context: 上下文信息
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 获取必要参数
        current_chapter = self.interaction_agent.current_chapter
        new_chapter = current_chapter + 1
        
        # 获取图像API配置
        access_key_id = context.get('access_key_id')
        secret_key = context.get('secret_key')
        base_url = context.get('base_url')
        auto_image = context.get('auto_image', True)
        
        # 获取语音API配置
        voice_app_id = context.get('voice_app_id') or self.config.get('voice_app_id')
        voice_token = context.get('voice_token') or self.config.get('voice_token')
        auto_voice = context.get('auto_voice', True)
        
        # 获取新章节摘要
        chapter_summary = self._get_chapter_summary(new_chapter)
        
        # 获取新章节事件
        chapter_events = self._get_chapter_events(new_chapter)
        
        # 过渡到新章节
        self.interaction_agent.transition_to_new_chapter(
            new_chapter=new_chapter,
            chapter_summary=chapter_summary,
            chapter_events=chapter_events
        )
        
        # 开始新章节交互
        scene = self.interaction_agent.start_interaction()
        
        # 自动生成图像（如果配置了）
        image_url = None
        remote_url = None
        if auto_image and access_key_id and secret_key:
            image_config = {
                'access_key_id': access_key_id,
                'secret_key': secret_key,
                'base_url': base_url
            }
            
            try:
                image_result = self.interaction_agent.generate_image_for_scene(
                    scene_id=None,  # 使用当前场景
                    style=None,  # 自动确定风格
                    image_config=image_config
                )
                
                # 提取图像URL
                if image_result and image_result.get('status') == 'success':
                    image_url = image_result.get('image_url')
                    remote_url = image_result.get('remote_url')
            except Exception as e:
                logger.warning(f"自动生成图像失败: {str(e)}")
        
        # 自动生成语音（如果配置了）
        audio_result = None
        logger.info(f"[DEBUG] auto_voice={auto_voice}, voice_app_id={voice_app_id}, voice_token={'YES' if voice_token else 'NO'}")
        logger.info(f"[DEBUG] adapter配置中的语音设置: voice_app_id={self.config.get('voice_app_id')}, voice_token={'YES' if self.config.get('voice_token') else 'NO'}")
        if auto_voice and voice_app_id and voice_token:
            logger.info("[DEBUG] 进入自动生成语音分支 (_next_chapter)")
            try:
                # 确保语音服务初始化
                if not self.interaction_agent.voice_service:
                    logger.info("[DEBUG] 语音服务未初始化，尝试初始化")
                    try:
                        from agent.services.voice_service import VoiceService
                        self.interaction_agent.voice_service = VoiceService(
                            app_id=voice_app_id,
                            token=voice_token,
                            llm_client=self.client,
                            llm_model=self.llm_model
                        )
                        logger.info(f"[DEBUG] 实时初始化语音服务结果: {self.interaction_agent.voice_service is not None}")
                    except Exception as e:
                        logger.exception(f"[DEBUG] 实时初始化语音服务失败: {str(e)}")
                
                logger.info("新章节 - 开始自动生成语音...")
                # 传递当前场景对象scene
                audio_result = self.interaction_agent.generate_audio_for_scene(scene)
                
                # 记录详细的结果信息
                if audio_result:
                    logger.info(f"语音生成结果: {audio_result.get('status')}, 对话数量: {len(audio_result.get('dialogues', []))}")
                    if audio_result.get('status') != 'success':
                        logger.warning(f"语音生成未成功: {audio_result.get('message', '未知错误')}")
                else:
                    logger.warning("语音生成返回空结果")
            except Exception as e:
                logger.exception(f"自动生成语音失败: {str(e)}")
        
        # 返回结果
        result = {
            "status": "success",
            "scene": scene,
            "character_name": self.interaction_agent.character_name,
            "chapter": new_chapter,
            "document_id": self.interaction_agent.document_id,
            "message": f"已进入第{new_chapter}章"
        }
        
        # 添加图像URL（如果有）
        if image_url:
            result["image_url"] = image_url
        if remote_url:
            result["remote_url"] = remote_url
        
        # 添加语音结果（如果有）
        if audio_result and audio_result.get('status') == 'success':
            result["audio_result"] = audio_result
        
        return result
    
    def _jump_to_chapter(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """跳转到指定章节
        
        Args:
            context: 上下文信息
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 获取必要参数
        chapter = context.get('chapter')
        
        # 获取图像API配置
        access_key_id = context.get('access_key_id')
        secret_key = context.get('secret_key')
        base_url = context.get('base_url')
        auto_image = context.get('auto_image', True)
        
        # 获取语音API配置
        voice_app_id = self.config.get('voice_app_id')
        voice_token = self.config.get('voice_token')
        auto_voice = context.get('auto_voice', True)
        
        if not chapter:
            return {
                "status": "error",
                "message": "章节编号不能为空"
            }
            
        # 获取章节摘要
        chapter_summary = self._get_chapter_summary(chapter)
        
        # 获取章节事件
        chapter_events = self._get_chapter_events(chapter)
        
        # 过渡到指定章节
        self.interaction_agent.transition_to_new_chapter(
            new_chapter=chapter,
            chapter_summary=chapter_summary,
            chapter_events=chapter_events
        )
        
        # 开始新章节交互
        scene = self.interaction_agent.start_interaction()
        
        # 自动生成图像（如果配置了）
        image_url = None
        remote_url = None
        if auto_image and access_key_id and secret_key:
            image_config = {
                'access_key_id': access_key_id,
                'secret_key': secret_key,
                'base_url': base_url
            }
            
            try:
                image_result = self.interaction_agent.generate_image_for_scene(
                    scene_id=None,  # 使用当前场景
                    style=None,  # 自动确定风格
                    image_config=image_config
                )
                
                # 提取图像URL
                if image_result and image_result.get('status') == 'success':
                    image_url = image_result.get('image_url')
                    remote_url = image_result.get('remote_url')
            except Exception as e:
                logger.warning(f"自动生成图像失败: {str(e)}")
        
        # 返回结果
        result = {
            "status": "success",
            "scene": scene,
            "character_name": self.interaction_agent.character_name,
            "chapter": chapter,
            "document_id": self.interaction_agent.document_id,
            "message": f"已跳转到第{chapter}章"
        }
        
        # 添加图像URL（如果有）
        if image_url:
            result["image_url"] = image_url
        if remote_url:
            result["remote_url"] = remote_url
        
        return result
    
    def _search_story_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """搜索故事相关信息
        
        Args:
            context: 上下文信息
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 获取必要参数
        query = context.get('query')
        
        if not query:
            return {
                "status": "error",
                "message": "查询不能为空"
            }
            
        # 默认返回空结果，暂不支持搜索功能
        return {
            "status": "success",
            "results": [],
            "message": "搜索功能暂不支持"
        }
    
    def _get_character_info(self, character_name: str) -> Dict[str, Any]:
        """获取角色信息
        
        Args:
            character_name: 角色名称
            
        Returns:
            Dict[str, Any]: 角色信息
        """
        # 从characters中获取角色信息
        return self.characters.get(character_name, {})
    
    def _get_chapter_summary(self, chapter: int) -> Dict[str, Any]:
        """获取章节摘要
        
        Args:
            chapter: 章节编号
            
        Returns:
            Dict[str, Any]: 章节摘要
        """
        # 从chapter_summaries中获取章节摘要
        for summary in self.chapter_summaries:
            if summary.get('chapter_num') == chapter:
                return summary
                
        return {}
    
    def _get_chapter_events(self, chapter: int) -> List[Dict[str, Any]]:
        """获取章节事件
        
        Args:
            chapter: 章节编号
            
        Returns:
            List[Dict[str, Any]]: 章节事件
        """
        # 从plots中获取相关章节的事件
        return [event for event in self.plots if event.get('chapter') == chapter]
    
    def set_voice_app_id(self, app_id: str, token: str = None) -> Dict[str, Any]:
        """设置语音服务AppID和Token
        
        Args:
            app_id: 火山引擎语音合成AppID
            token: 火山引擎语音合成Token
            
        Returns:
            Dict[str, Any]: 设置结果
        """
        if not self.interaction_agent:
            return {
                "status": "error",
                "message": "交互代理未初始化"
            }
        
        # 更新配置
        if app_id:
            self.config['voice_app_id'] = app_id
        if token:
            self.config['voice_token'] = token
            
        # 转发到交互代理
        try:
            result = self.interaction_agent.set_voice_app_id(app_id, token)
            logger.info(f"语音服务配置更新结果: {result['status']} - {result['message']}")
            return result
        except Exception as e:
            logger.exception(f"更新语音服务配置失败: {str(e)}")
            return {
                "status": "error",
                "message": f"更新语音服务配置失败: {str(e)}"
            }
    
    def generate_audio_for_scene(self, scene: Dict[str, Any] = None) -> Dict[str, Any]:
        """为场景生成语音
        
        Args:
            scene: 场景信息，默认使用当前场景
            
        Returns:
            Dict[str, Any]: 语音生成结果
        """
        try:
            if not self.interaction_agent.voice_service:
                logger.warning("语音服务未初始化，无法生成语音")
                return {
                    "status": "error",
                    "message": "语音服务未初始化"
                }
                
            if not self.config.get('voice_app_id') or not self.config.get('voice_token'):
                logger.warning("未配置语音服务AppID或Token，无法生成语音")
                return {
                    "status": "error",
                    "message": "未配置语音服务AppID或Token"
                }
                
            logger.info(f"开始生成场景语音, 场景ID: {scene.get('interaction_id') if scene else '当前场景'}")
            
            if scene:
                # 创建临时场景ID用于生成语音
                temp_scene_id = f"temp_{int(time.time())}"
                # 添加场景ID
                scene['interaction_id'] = temp_scene_id
                # 调用生成方法
                result = self.interaction_agent.generate_audio_for_scene(temp_scene_id)
                logger.info(f"生成场景语音完成: {result.get('status')}")
                return result
            else:
                # 使用当前场景
                result = self.interaction_agent.generate_audio_for_scene()
                logger.info(f"生成场景语音完成: {result.get('status')}")
                return result
        except Exception as e:
            logger.exception(f"生成场景语音失败: {str(e)}")
            return {
                "status": "error",
                "message": f"生成场景语音失败: {str(e)}"
            }
    
    def test_voice_service(self) -> Dict[str, Any]:
        """测试语音服务配置
        
        Returns:
            Dict[str, Any]: 测试结果
        """
        result = {
            "status": "error",
            "message": "未初始化语音服务"
        }
        
        if not self.interaction_agent:
            result["message"] = "交互代理未初始化"
            return result
        
        if not self.interaction_agent.voice_service:
            result["message"] = "语音服务未初始化"
            return result
        
        # 获取认证信息
        auth_info = self.interaction_agent.voice_service.debug_auth_info()
        result["auth_info"] = auth_info
        
        # 检查配置
        if not auth_info["app_id"]:
            result["message"] = "未设置语音AppID"
            return result
        
        if not auth_info["token_set"]:
            result["message"] = "未设置语音Token"
            return result
        
        # 尝试生成简短的测试语音
        try:
            test_text = "语音服务测试"
            audio_path = self.interaction_agent.voice_service.generate_speech(
                test_text, 
                voice_type="default",
                return_path=True
            )
            
            if audio_path:
                result["status"] = "success"
                result["message"] = "语音服务测试成功"
                result["audio_path"] = audio_path
            else:
                result["message"] = "语音生成失败"
        except Exception as e:
            result["message"] = f"语音服务测试异常: {str(e)}"
            logger.exception("语音服务测试异常")
        
        return result 