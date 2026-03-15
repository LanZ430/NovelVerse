from typing import Dict, Any, List, Optional, Tuple
import logging
import json
from pathlib import Path
import time
from .base_agent import BaseAgent
from openai import OpenAI
import re

logger = logging.getLogger(__name__)

class InteractionAgent(BaseAgent):
    """交互代理，负责处理用户与故事的交互"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化交互代理
        
        Args:
            config: 配置信息，包括：
                - data_dir: 数据存储目录
                - llm_api_key: 大语言模型API密钥
                - llm_base_url: 大语言模型API基础URL
                - llm_model: 大语言模型名称
        """
        super().__init__(config)
        self.data_dir = Path(self.config.get('data_dir', './data'))
        self.interactions_dir = self.data_dir / 'interactions'
        self.state_file = None
        self.document_id = None
        self.character_name = None
        self.current_chapter = 1
        self.interaction_history = []
        self.current_state = {
            'progress': 0,
            'choices': [],
            'divergences': []
        }
        
        # 长期记忆存储
        self.memory_store = []
        
        # 设置LLM客户端
        llm_api_key = self.config.get('llm_api_key')
        llm_base_url = self.config.get('llm_base_url', 'https://api.deepseek.com')
        self.client = OpenAI(
            api_key=llm_api_key,
            base_url=llm_base_url
        )
        self.llm_model = self.config.get('llm_model', 'deepseek-chat')
        
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
            self.interactions_dir.mkdir(parents=True, exist_ok=True)
            
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
            context: 上下文信息，包括：
                - document_id: 文档ID
                - character_name: 角色名称
                - chapter: 章节编号
                - knowledge_base: 知识库
                - access_key_id: 图像生成API密钥ID（可选）
                - secret_key: 图像生成API密钥（可选）
                - base_url: 图像生成API基础URL（可选）
                - auto_image: 是否自动生成图像（可选，默认True）
                
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
            
        # 设置交互状态
        self.document_id = document_id
        self.character_name = character_name
        self.current_chapter = chapter
        
        # 检测文档语言
        self.document_language = self._detect_document_language(document_id)
        
        # 加载知识库
        if knowledge_base:
            self.knowledge_base = knowledge_base
            self.characters = knowledge_base.get('characters', {})
            self.settings = knowledge_base.get('settings', {})
            self.plots = knowledge_base.get('plots', [])
            self.chapter_summaries = knowledge_base.get('chapter_summaries', [])
        else:
            # 从文件加载知识库
            self._load_knowledge_base()
            
        # 初始化交互状态文件
        self.state_file = self.interactions_dir / f"{document_id}_{character_name}_state.json"
        
        # 如果状态文件存在，加载之前的交互状态
        if self.state_file.exists():
            self._load_interaction_state()
        else:
            # 初始化新的交互状态
            self.interaction_history = []
            self.current_state = {
                'progress': 0,
                'choices': [],
                'divergences': []
            }
            self._save_interaction_state()
            
        # 生成初始场景
        try:
            initial_scene = self._generate_scene()
            
            # 保存交互状态
            self.interaction_history.append({
                'timestamp': self._get_current_timestamp(),
                'type': 'scene',
                'content': initial_scene
            })
            self._save_interaction_state()
            
            # 构建返回结果
            result = {
                "status": "success",
                "message": "交互已开始",
                "scene": initial_scene,
                "character_name": self.character_name,
                "chapter": self.current_chapter,
                "document_id": self.document_id
            }
            
            # 如果开启自动生成图像，尝试生成
            if auto_image and access_key_id and secret_key:
                image_result = self._auto_generate_image(initial_scene, access_key_id, secret_key, base_url)
                
                # 如果生成成功，添加图像信息
                if image_result and image_result.get('status') == 'success':
                    result['image_url'] = image_result.get('image_url')
                    result['remote_url'] = image_result.get('remote_url', '')
                    result['has_image'] = True
                    result['image_style'] = image_result.get('style', 'realistic')
            
            return result
            
        except Exception as e:
            logger.exception(f"生成初始场景失败: {str(e)}")
            return {
                "status": "error",
                "message": f"开始交互失败: {str(e)}"
            }
    
    def _continue_interaction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """继续交互
        
        Args:
            context: 上下文信息，包括：
                - user_input: 用户输入
                - accept_deviation: 是否接受情节偏离
                - force_continue: UI传递的是否强制继续参数
                - access_key_id: 图像生成API密钥ID（可选）
                - secret_key: 图像生成API密钥（可选）
                - base_url: 图像生成API基础URL（可选）
                - auto_image: 是否自动生成图像（可选，默认True）
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        user_input = context.get('user_input')
        accept_deviation = context.get('accept_deviation', False)
        force_continue = context.get('force_continue', False)  # 从UI传递的参数
        
        # 获取图像API配置
        access_key_id = context.get('access_key_id')
        secret_key = context.get('secret_key')
        base_url = context.get('base_url')
        auto_image = context.get('auto_image', True)  # 默认开启自动生成图像
        
        if not user_input:
            return {
                "status": "error",
                "message": "用户输入不能为空"
            }
            
        if not self.document_id or not self.character_name:
            return {
                "status": "error",
                "message": "请先开始交互"
            }
            
        # 获取上一个场景
        last_scene = None
        for item in reversed(self.interaction_history):
            if item.get('type') == 'scene':
                last_scene = item.get('content')
                break
                
        if not last_scene:
            return {
                "status": "error",
                "message": "找不到上一个场景"
            }
            
        # 如果用户接受偏离或强制继续，直接调用偏离处理函数
        # 但只有高偏离度才生成偏离结局，低偏离度则正常继续
        if force_continue:
            # 先获取最后一次偏离的描述来判断偏离等级
            last_divergence = None
            divergence_level = 0
            if self.current_state.get('divergences'):
                last_divergence = self.current_state['divergences'][-1]
                divergence_level = last_divergence.get('level', 0)
            
            # 如果是高偏离度（≥3）才生成偏离结局，否则正常继续
            if divergence_level >= 3:
                deviation_result = self._continue_with_deviation(user_input, last_scene)
                
                # 如果开启自动生成图像并且生成成功，添加图像信息
                if auto_image and deviation_result.get('status') == 'deviated_ending' and access_key_id and secret_key:
                    # 获取生成的偏离结局场景
                    deviated_scene = deviation_result.get('scene')
                    if deviated_scene:
                        # 自动生成图像
                        image_result = self._auto_generate_image(deviated_scene, access_key_id, secret_key, base_url)
                        
                        # 如果生成成功，添加图像信息到返回结果
                        if image_result.get('status') == 'success':
                            deviation_result['image_url'] = image_result.get('image_url')
                            deviation_result['remote_url'] = image_result.get('remote_url', '')
                            deviation_result['has_image'] = True
                
                return deviation_result
            else:
                # 低偏离度直接按照正常流程处理，但标记为已接受偏离
                accept_deviation = True
            
        # 评估用户输入
        try:
            evaluation = self._evaluate_user_input(user_input, last_scene)
            
            # 保存用户输入和评估结果
            self.interaction_history.append({
                'timestamp': self._get_current_timestamp(),
                'type': 'user_input',
                'content': user_input,
                'evaluation': evaluation
            })
            
            # 检查是否存在重大偏离
            divergence_level = evaluation.get('divergence', {}).get('level', 0)
            
            # 统一使用偏离等级3作为警告门槛
            if divergence_level >= 3 and not accept_deviation:
                # 记录偏离
                self.current_state['divergences'].append({
                    'timestamp': self._get_current_timestamp(),
                    'description': evaluation.get('divergence', {}).get('description', ''),
                    'level': divergence_level
                })
                
                # 需要警告用户
                self._save_interaction_state()
                
                return {
                    "status": "warning",
                    "message": "检测到重大故事偏离",
                    "divergence": evaluation.get('divergence', {}),
                    "should_continue": False,
                    "character_name": self.character_name,
                    "chapter": self.current_chapter
                }
                
            # 如果偏离不是很严重或用户已接受偏离，继续生成
            # 记录选择
            self.current_state['choices'].append({
                'timestamp': self._get_current_timestamp(),
                'content': user_input,
                'evaluation': evaluation
            })
            
            # 如果有低偏离度且用户明确接受，标记该偏离已被接受
            if divergence_level > 0 and accept_deviation:
                # 记录偏离，但标记为用户已接受
                self.current_state['divergences'].append({
                    'timestamp': self._get_current_timestamp(),
                    'description': evaluation.get('divergence', {}).get('description', ''),
                    'level': divergence_level,
                    'user_accepted': True
                })
            
            # 更新进度
            if 'progress' in evaluation:
                self.current_state['progress'] = evaluation['progress']
                
            # 保存交互状态
            self._save_interaction_state()
            
            # 生成新场景
            new_scene = self._generate_scene(user_input, evaluation)
            
            # 更新记忆库
            self._update_memory_store(new_scene)
            
            # 保存新场景
            self.interaction_history.append({
                'timestamp': self._get_current_timestamp(),
                'type': 'scene',
                'content': new_scene
            })
            self._save_interaction_state()
            
            # 检查是否应该进入下一章
            should_proceed = evaluation.get('should_proceed_chapter', False)
            
            # 如果开启自动生成图像，尝试生成
            image_result = None
            if auto_image and access_key_id and secret_key:
                image_result = self._auto_generate_image(new_scene, access_key_id, secret_key, base_url)
                
            # 构建返回结果
            result = {
                "status": "success",
                "message": "交互继续",
                "scene": new_scene,
                "evaluation": evaluation,
                "should_proceed_chapter": should_proceed,
                "character_name": self.character_name,
                "chapter": self.current_chapter,
                "progress": self.current_state['progress']
            }
            
            # 如果生成了图像，添加图像信息
            if image_result and image_result.get('status') == 'success':
                result['image_url'] = image_result.get('image_url')
                result['remote_url'] = image_result.get('remote_url', '')
                result['has_image'] = True
                result['image_style'] = image_result.get('style', 'realistic')
            
            return result
            
        except Exception as e:
            logger.exception(f"处理用户输入失败: {str(e)}")
            return {
                "status": "error",
                "message": f"继续交互失败: {str(e)}"
            }
    
    def _continue_with_deviation(self, user_input: str, last_scene: Dict[str, Any]) -> Dict[str, Any]:
        """处理用户明确选择继续偏离主线的情况
        
        Args:
            user_input: 用户输入
            last_scene: 上一个场景
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        logger.info(f"用户选择继续偏离主线的故事: {user_input}")
        
        # 获取最后一次偏离的描述
        last_divergence = None
        if self.current_state.get('divergences'):
            last_divergence = self.current_state['divergences'][-1]
            
            # 添加用户确认继续偏离的标记
            last_divergence['user_accepted'] = True
        
        # 记录用户选择接受偏离的决定
        self.interaction_history.append({
            'timestamp': self._get_current_timestamp(),
            'type': 'user_input',
            'content': user_input,
            'accepted_deviation': True
        })
        
        # 获取角色信息
        character_info = self._get_character_info()
        
        # 获取章节摘要
        chapter_summary = self._get_chapter_summary()
        
        # 获取跨章节记忆
        cross_chapter_memory = self._get_cross_chapter_memory()
        
        # 生成交互ID
        interaction_id = f"ch{self.current_chapter}_dev_{int(time.time())}"
        
        # 构建特殊的偏离结局提示
        prompt = f"""你是一个沉浸式小说交互系统。用户已明确选择继续一个偏离主线的故事方向。基于用户的选择，生成一个偏离主线但符合逻辑的结局场景。

### 基本信息
- 角色：{self.character_name}
- 当前章节：{self.current_chapter}
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
1. 必须严格从{self.character_name}的第一人称视角描述场景和内心感受
2. 创建一个有情感和细节的结局场景（300-400字），具有一定的完整性和结局感
3. 基于用户的选择，生成一个虽然偏离原故事主线，但在逻辑上合理自洽的结局
4. 确保情绪状态和场景描述与角色身份一致
5. 必须描述用户扮演的对话者的反应、表情和态度变化
6. 环境应该随着情节的发展而变化，描述光线、气氛、声音等细节的变化
7. 标记这是一个偏离主线的结局，让用户知道这条叙事支线已经结束
8. 提供一个情感上有共鸣的收尾，可以是开放式的但要有一定的完结感

请以JSON格式返回，包含以下字段：
- narrative: 从{self.character_name}第一人称视角的结局场景描述（必须使用"我"，不能用"{self.character_name}"）
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
                if not self._validate_first_person_perspective(narrative):
                    logger.warning("生成的内容不是第一人称视角，进行修正")
                    scene['narrative'] = self._fix_perspective(narrative, self.character_name)
                
                # 处理情感状态
                if isinstance(scene.get('emotion_state'), dict):
                    emotion_state = scene['emotion_state']
                    if self.character_name in emotion_state:
                        emotion_state['我'] = emotion_state.pop(self.character_name)
                
                # 设置进度为100%
                if 'progress_info' not in scene:
                    scene['progress_info'] = {
                        "current_scene": "偏离主线结局",
                        "progress": 100,
                        "is_ending": True
                    }
                
                # 更新记忆库
                self._update_memory_store(scene)
                
                # 保存结局场景
                self.interaction_history.append({
                    'timestamp': self._get_current_timestamp(),
                    'type': 'scene',
                    'content': scene,
                    'is_deviated_ending': True
                })
                
                # 更新状态
                self.current_state['progress'] = 100
                self.current_state['choices'].append({
                    'timestamp': self._get_current_timestamp(),
                    'content': user_input,
                    'led_to_deviation': True
                })
                
                # 保存交互状态
                self._save_interaction_state()
                
                return {
                    "status": "deviated_ending",
                    "message": "已生成偏离主线的结局",
                    "scene": scene,
                    "character_name": self.character_name,
                    "chapter": self.current_chapter,
                    "progress": 100,
                    "is_ending": True
                }
                
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
                        return {
                            "status": "deviated_ending",
                            "message": "已生成偏离主线的结局",
                            "scene": scene,
                            "character_name": self.character_name,
                            "chapter": self.current_chapter,
                            "progress": 100,
                            "is_ending": True
                        }
                    except json.JSONDecodeError:
                        logger.error("无法解析提取的JSON内容")
                
                # 返回一个基本的结局场景
                fallback_scene = {
                    "narrative": f"我（{self.character_name}）的选择让事情走向了一个不同的方向。[此处是系统生成的偏离主线结局]",
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
                
                return {
                    "status": "deviated_ending",
                    "message": "已生成偏离主线的结局",
                    "scene": fallback_scene,
                    "character_name": self.character_name,
                    "chapter": self.current_chapter,
                    "progress": 100,
                    "is_ending": True
                }
                
        except Exception as e:
            logger.exception(f"生成偏离结局场景失败: {str(e)}")
            return {
                "status": "error",
                "message": f"生成偏离结局失败: {str(e)}"
            }
    
    def _stop_interaction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """停止交互
        
        Args:
            context: 上下文信息
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 保存当前状态
        if self.document_id and self.character_name:
            self._save_interaction_state()
            
        # 清理状态
        self.document_id = None
        self.character_name = None
        self.current_chapter = 1
        self.interaction_history = []
        self.current_state = {
            'progress': 0,
            'choices': [],
            'divergences': []
        }
        self.state_file = None
        
        return {
            "status": "success",
            "message": "交互已停止"
        }
    
    def _next_chapter(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """进入下一章节
        
        Args:
            context: 上下文信息，包括：
                - access_key_id: 图像生成API密钥ID（可选）
                - secret_key: 图像生成API密钥（可选）
                - base_url: 图像生成API基础URL（可选）
                - auto_image: 是否自动生成图像（可选，默认True）
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 获取图像API配置
        access_key_id = context.get('access_key_id')
        secret_key = context.get('secret_key')
        base_url = context.get('base_url')
        auto_image = context.get('auto_image', True)  # 默认开启自动生成图像
        
        if not self.document_id or not self.character_name:
            return {
                "status": "error",
                "message": "请先开始交互"
            }
            
        # 保存当前章节状态
        self._save_interaction_state()
        
        # 生成章节摘要并保存为记忆
        self._generate_chapter_summary()
        
        # 更新章节
        self.current_chapter += 1
        
        # 重置交互状态
        self.interaction_history = []
        self.current_state = {
            'progress': 0,
            'choices': [],
            'divergences': []
        }
        
        # 生成新章节的初始场景
        try:
            initial_scene = self._generate_scene()
            
            # 保存交互状态
            self.interaction_history.append({
                'timestamp': self._get_current_timestamp(),
                'type': 'scene',
                'content': initial_scene
            })
            self._save_interaction_state()
            
            # 构建返回结果
            result = {
                "status": "success",
                "message": f"已进入第{self.current_chapter}章",
                "scene": initial_scene,
                "character_name": self.character_name,
                "chapter": self.current_chapter,
                "document_id": self.document_id
            }
            
            # 如果开启自动生成图像，尝试生成
            if auto_image and access_key_id and secret_key:
                image_result = self._auto_generate_image(initial_scene, access_key_id, secret_key, base_url)
                
                # 如果生成成功，添加图像信息
                if image_result and image_result.get('status') == 'success':
                    result['image_url'] = image_result.get('image_url')
                    result['remote_url'] = image_result.get('remote_url', '')
                    result['has_image'] = True
                    result['image_style'] = image_result.get('style', 'realistic')
            
            return result
            
        except Exception as e:
            logger.exception(f"生成新章节场景失败: {str(e)}")
            return {
                "status": "error",
                "message": f"进入下一章节失败: {str(e)}"
            }
    
    def _generate_chapter_summary(self) -> None:
        """生成章节摘要并添加到记忆库"""
        # 获取本章节的所有场景
        scenes = [item.get('content', {}) for item in self.interaction_history if item.get('type') == 'scene']
        if not scenes:
            return
            
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
- 角色：{self.character_name}
- 章节：第{self.current_chapter}章

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
            response = self.client.chat.completions.create(
                model=self.llm_model,
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
                        'content': f"第{self.current_chapter}章摘要：{summary}",
                        'chapter': self.current_chapter,
                        'character': self.character_name,
                        'timestamp': self._get_current_timestamp(),
                        'importance': 5,  # 章节摘要很重要
                        'type': 'chapter_summary'
                    })
                
                # 添加关键线索到记忆库
                key_clues = summary_data.get('key_clues', [])
                for i, clue in enumerate(key_clues):
                    self.memory_store.append({
                        'content': f"第{self.current_chapter}章线索：{clue}",
                        'chapter': self.current_chapter,
                        'character': self.character_name,
                        'timestamp': self._get_current_timestamp(),
                        'importance': 4.5 - (i * 0.2),  # 线索按顺序略微降低重要性
                        'type': 'key_clue'
                    })
                    
                logger.info(f"已生成第{self.current_chapter}章摘要和{len(key_clues)}个关键线索")
                
            except json.JSONDecodeError:
                logger.warning("LLM返回的章节摘要不是有效的JSON格式")
                
        except Exception as e:
            logger.error(f"生成章节摘要失败: {str(e)}")
            
    def _jump_to_chapter(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """跳转到指定章节
        
        Args:
            context: 上下文信息，包括：
                - chapter: 目标章节编号
                - access_key_id: 图像生成API密钥ID（可选）
                - secret_key: 图像生成API密钥（可选）
                - base_url: 图像生成API基础URL（可选）
                - auto_image: 是否自动生成图像（可选，默认True）
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        target_chapter = context.get('chapter')
        
        # 获取图像API配置
        access_key_id = context.get('access_key_id')
        secret_key = context.get('secret_key')
        base_url = context.get('base_url')
        auto_image = context.get('auto_image', True)  # 默认开启自动生成图像
        
        if not target_chapter or not isinstance(target_chapter, int) or target_chapter <= 0:
            return {
                "status": "error",
                "message": "无效的章节编号"
            }
            
        if not self.document_id or not self.character_name:
            return {
                "status": "error",
                "message": "请先开始交互"
            }
            
        # 保存当前章节状态
        self._save_interaction_state()
        
        # 更新章节
        self.current_chapter = target_chapter
        
        # 重置交互状态
        self.interaction_history = []
        self.current_state = {
            'progress': 0,
            'choices': [],
            'divergences': []
        }
        
        # 尝试加载目标章节的状态
        target_state_file = self.interactions_dir / f"{self.document_id}_{self.character_name}_chapter_{target_chapter}_state.json"
        if target_state_file.exists():
            try:
                with open(target_state_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
                    self.interaction_history = state_data.get('interaction_history', [])
                    self.current_state = state_data.get('current_state', {
                        'progress': 0,
                        'choices': [],
                        'divergences': []
                    })
                    
                # 如果有历史交互，提取最后一个场景
                last_scene = None
                for item in reversed(self.interaction_history):
                    if item.get('type') == 'scene':
                        last_scene = item.get('content')
                        break
                        
                if last_scene:
                    result = {
                        "status": "success",
                        "message": f"已跳转到第{target_chapter}章",
                        "scene": last_scene,
                        "character_name": self.character_name,
                        "chapter": self.current_chapter,
                        "document_id": self.document_id,
                        "is_resumed": True
                    }
                    
                    # 如果开启自动生成图像，尝试生成
                    if auto_image and access_key_id and secret_key:
                        image_result = self._auto_generate_image(last_scene, access_key_id, secret_key, base_url)
                        
                        # 如果生成成功，添加图像信息
                        if image_result and image_result.get('status') == 'success':
                            result['image_url'] = image_result.get('image_url')
                            result['remote_url'] = image_result.get('remote_url', '')
                            result['has_image'] = True
                            result['image_style'] = image_result.get('style', 'realistic')
                    
                    return result
            except Exception as e:
                logger.error(f"加载目标章节状态失败: {str(e)}")
        
        # 如果没有历史状态或加载失败，生成新场景
        try:
            initial_scene = self._generate_scene()
            
            # 保存交互状态
            self.interaction_history.append({
                'timestamp': self._get_current_timestamp(),
                'type': 'scene',
                'content': initial_scene
            })
            self._save_interaction_state()
            
            # 构建返回结果
            result = {
                "status": "success",
                "message": f"已跳转到第{target_chapter}章",
                "scene": initial_scene,
                "character_name": self.character_name,
                "chapter": self.current_chapter,
                "document_id": self.document_id,
                "is_resumed": False
            }
            
            # 如果开启自动生成图像，尝试生成
            if auto_image and access_key_id and secret_key:
                image_result = self._auto_generate_image(initial_scene, access_key_id, secret_key, base_url)
                
                # 如果生成成功，添加图像信息
                if image_result and image_result.get('status') == 'success':
                    result['image_url'] = image_result.get('image_url')
                    result['remote_url'] = image_result.get('remote_url', '')
                    result['has_image'] = True
                    result['image_style'] = image_result.get('style', 'realistic')
            
            return result
        except Exception as e:
            logger.exception(f"生成章节场景失败: {str(e)}")
            return {
                "status": "error",
                "message": f"跳转到章节{target_chapter}失败: {str(e)}"
            }
    
    def _load_knowledge_base(self) -> None:
        """从文件加载知识库"""
        try:
            # 加载角色信息
            character_file = self.data_dir / 'characters' / self.document_id / "characters.json"
            if character_file.exists():
                with open(character_file, "r", encoding="utf-8") as f:
                    self.characters = json.load(f)
            
            # 加载设定信息
            setting_file = self.data_dir / 'settings' / self.document_id / "settings.json"
            if setting_file.exists():
                with open(setting_file, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
            
            # 加载情节信息
            plot_file = self.data_dir / 'plots' / self.document_id / "plots.json"
            if plot_file.exists():
                with open(plot_file, "r", encoding="utf-8") as f:
                    self.plots = json.load(f)
            
            # 加载摘要信息
            summary_dir = self.data_dir / 'summaries' / self.document_id
            if summary_dir.exists():
                self.chapter_summaries = []
                for summary_file in sorted(summary_dir.glob("summary_*.json")):
                    with open(summary_file, "r", encoding="utf-8") as f:
                        self.chapter_summaries.append(json.load(f))
            
            # 构建知识库
            self.knowledge_base = {
                "characters": self.characters,
                "settings": self.settings,
                "plots": self.plots,
                "chapter_summaries": self.chapter_summaries
            }
            
            logger.info(f"已加载文档 {self.document_id} 的知识库")
        except Exception as e:
            logger.error(f"加载知识库失败: {str(e)}")
    
    def _load_interaction_state(self) -> None:
        """加载交互状态"""
        if not self.state_file or not self.state_file.exists():
            return
            
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                self.interaction_history = state_data.get('interaction_history', [])
                self.current_state = state_data.get('current_state', {
                    'progress': 0,
                    'choices': [],
                    'divergences': []
                })
                # 加载记忆库
                self.memory_store = state_data.get('memory_store', [])
            
            logger.info(f"已加载交互状态: {self.state_file}")
        except Exception as e:
            logger.error(f"加载交互状态失败: {str(e)}")
    
    def _save_interaction_state(self) -> None:
        """保存交互状态"""
        if not self.state_file:
            chapter_specific = self.interactions_dir / f"{self.document_id}_{self.character_name}_chapter_{self.current_chapter}_state.json"
            self.state_file = chapter_specific
            
        try:
            # 确保目录存在
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存状态
            state_data = {
                'document_id': self.document_id,
                'character_name': self.character_name,
                'chapter': self.current_chapter,
                'last_updated': self._get_current_timestamp(),
                'interaction_history': self.interaction_history,
                'current_state': self.current_state,
                'memory_store': self.memory_store  # 保存记忆库
            }
            
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"已保存交互状态: {self.state_file}")
        except Exception as e:
            logger.error(f"保存交互状态失败: {str(e)}")
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳
        
        Returns:
            str: 时间戳字符串
        """
        import datetime
        return datetime.datetime.now().isoformat()
    
    def _get_character_info(self) -> Dict[str, Any]:
        """获取当前角色信息
        
        Returns:
            Dict[str, Any]: 角色信息
        """
        if not self.character_name or not self.characters:
            return {}
            
        return self.characters.get(self.character_name, {})
    
    def _get_chapter_summary(self) -> Dict[str, Any]:
        """获取当前章节摘要
        
        Returns:
            Dict[str, Any]: 章节摘要
        """
        if not self.chapter_summaries:
            return {}
            
        for summary in self.chapter_summaries:
            if summary.get('chapter_num') == self.current_chapter:
                return summary
                
        return {}
    
    def _get_chapter_events(self) -> List[Dict[str, Any]]:
        """获取当前章节事件
        
        Returns:
            List[Dict[str, Any]]: 章节事件列表
        """
        if not self.plots:
            return []
            
        return [event for event in self.plots if event.get('chapter') == self.current_chapter]
    
    def _get_cross_chapter_memory(self) -> List[Dict[str, Any]]:
        """获取跨章节记忆
        
        Returns:
            List[Dict[str, Any]]: 跨章节记忆列表
        """
        # 返回存储的长期记忆
        # 如果记忆超过20条，只返回最重要的20条
        if len(self.memory_store) > 20:
            return sorted(self.memory_store, key=lambda x: x.get('importance', 0), reverse=True)[:20]
        return self.memory_store
    
    def _update_memory_store(self, scene: Dict[str, Any]) -> None:
        """更新记忆库
        
        Args:
            scene: 场景信息，包含memory_update字段
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
                'chapter': self.current_chapter,
                'character': self.character_name,
                'timestamp': self._get_current_timestamp(),
                'importance': importance
            }
            
            # 防止重复记忆
            if not any(m['content'] == memory for m in self.memory_store):
                self.memory_store.append(memory_item)
    
    def _generate_scene(self, user_input: str = "", evaluation: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成场景
        
        Args:
            user_input: 用户输入
            evaluation: 评估结果
            
        Returns:
            Dict[str, Any]: 场景信息
        """
        # 获取角色信息
        character_info = self._get_character_info()
        
        # 获取章节摘要
        chapter_summary = self._get_chapter_summary()
        
        # 获取章节事件
        chapter_events = self._get_chapter_events()
        
        # 获取跨章节记忆
        cross_chapter_memory = self._get_cross_chapter_memory()
        
        # 获取当前交互状态
        current_progress = self.current_state.get('progress', 0)
        recent_choices = self.current_state.get('choices', [])[-3:] if self.current_state.get('choices') else []
        recent_divergences = self.current_state.get('divergences', [])[-2:] if self.current_state.get('divergences') else []
        
        # 生成交互ID
        interaction_id = f"ch{self.current_chapter}_{int(time.time())}"
        
        # 构建提示
        # 视角和语言指示
        perspective_instruction = ""
        if self.document_language == 'english':
            perspective_instruction = f"""IMPORTANT: The player has chosen to play as the character "{self.character_name}". All content must be generated from the first-person perspective of "{self.character_name}".
Use "I" instead of "you" to refer to {self.character_name}, and refer to other characters as "you" or by their names.
The description should reflect what {self.character_name} sees, hears, and feels, expressing {self.character_name}'s thoughts and feelings.

You MUST generate ALL content in English only. Match your writing style to the original English text.
Use appropriate English vocabulary, idioms, and expressions. DO NOT use any Chinese in your response."""
        else:
            perspective_instruction = f"""重要：玩家已选择扮演角色"{self.character_name}"，所有内容必须从"{self.character_name}"的第一人称视角生成。
使用"我"而不是"你"来指代{self.character_name}，将其他角色作为"你"或使用他们的名字来指代。
描述应反映{self.character_name}看到、听到、感受到的一切，体现{self.character_name}的思想和感受。

场景描述必须同时包含交互对象（用户角色）的反应和情绪变化，以及环境随情节发展的变化。
交互对象不仅是倾听者，也是具有性格特征和反应的角色，要描述其行为、表情和态度随情节发展而变化。
环境细节（如光线、气氛、周围物体）应该根据剧情的发展相应变化，增强沉浸感。"""
        
        # 基于是否有用户输入构建不同的提示
        if user_input and evaluation:
            # 继续场景
            prompt = f"""你是一个沉浸式小说交互系统。基于用户的选择，生成新的场景。严格遵循以下要求：

{perspective_instruction}

### 基本信息
- 角色：{self.character_name}
- 当前章节：{self.current_chapter}
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
1. 必须严格从{self.character_name}的第一人称视角描述场景和内心感受
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
- narrative: 从{self.character_name}第一人称视角的场景描述（必须使用"我"，不能用"{self.character_name}"），包含交互对象的反应和环境变化
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
        else:
            # 初始场景
            prompt = f"""你是一个沉浸式小说交互系统。生成一个章节的初始场景。严格遵循以下要求：

{perspective_instruction}

### 基本信息
- 角色：{self.character_name}
- 当前章节：{self.current_chapter}
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
1. 必须严格从{self.character_name}的第一人称视角描述场景和内心感受
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
- narrative: 从{self.character_name}第一人称视角的场景描述（必须使用"我"，不能用"{self.character_name}"），包含交互对象的特征和环境细节
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
                if not self._validate_first_person_perspective(narrative):
                    logger.warning("生成的内容不是第一人称视角，进行修正")
                    scene['narrative'] = self._fix_perspective(narrative, self.character_name)
                
                # 处理情感状态
                if isinstance(scene.get('emotion_state'), dict):
                    emotion_state = scene['emotion_state']
                    if self.character_name in emotion_state:
                        emotion_state['我'] = emotion_state.pop(self.character_name)
                
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
                    "narrative": f"我（{self.character_name}）站在这里，思考着接下来该怎么做。",
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
    
    def _evaluate_user_input(self, user_input: str, last_scene: Dict[str, Any]) -> Dict[str, Any]:
        """评估用户输入
        
        Args:
            user_input: 用户输入
            last_scene: 上一个场景
            
        Returns:
            Dict[str, Any]: 评估结果
        """
        # 获取角色信息
        character_info = self._get_character_info()
        
        # 获取章节摘要
        chapter_summary = self._get_chapter_summary()
        
        # 获取章节事件
        chapter_events = self._get_chapter_events()
        
        # 获取相关记忆和线索
        related_memories = self._get_related_memories(user_input)
        
        # 获取交互ID
        interaction_id = last_scene.get('interaction_id', f"ch{self.current_chapter}_{int(time.time())}")
        
        # 获取当前进度
        current_progress = self.current_state.get('progress', 0)
        if last_scene.get('progress_info', {}).get('progress'):
            current_progress = last_scene.get('progress_info', {}).get('progress')
            
        # 获取最近的偏离
        recent_divergences = self.current_state.get('divergences', [])[-2:] if self.current_state.get('divergences') else []
        
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
        prompt = ""
        if self.document_language == 'english':
            prompt = f"""Evaluate the user's choice in an interactive story and analyze its impact.

### Basic Information
- Character: {self.character_name}
- Chapter: {self.current_chapter}
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
3. **Character Consistency**: Does the choice align with {self.character_name}'s personality? Does it foster character development?
4. **Future Impact**: Predict 2-3 possible subsequent developments.
5. **Need for Correction**: If the choice deviates too much, should it be guided back to the main storyline?
6. **Progress Assessment**: What percentage of the story progress (0-100%) does this choice advance to?

The evaluation result must be in strictly parsable JSON format:
{json.dumps(evaluation_template, ensure_ascii=False, indent=2)}"""
        else:
            prompt = f"""评估用户在小说交互中做出的选择，分析其对故事的影响。

### 基本信息
- 角色: {self.character_name}
- 章节: {self.current_chapter}
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
3. **角色一致性**: 选择是否符合{self.character_name}的性格？是否促进角色发展？
4. **后续影响**: 预测2-3个可能的后续发展。
5. **是否需要修正**: 如果选择太过偏离，是否需要引导回主线？
6. **进度评估**: 这个选择将故事进度推进到了多少百分比(0-100)？

评估结果必须是严格可解析的JSON格式:
{json.dumps(evaluation_template, ensure_ascii=False, indent=2)}"""
        
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
    
    def _validate_first_person_perspective(self, text: str) -> bool:
        """验证文本是否使用第一人称视角
        
        Args:
            text: 文本内容
            
        Returns:
            bool: 是否是第一人称视角
        """
        # 检查是否包含"我"而不是角色名称作为主语
        has_first_person = "我" in text and "我的" in text
        has_character_name_as_subject = re.search(f"{self.character_name}[^，。；：？！]*[是|走|看|说|想|感觉|觉得]", text) is not None
        
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
    
    def generate_image_from_scene(self, scene: Dict[str, Any], access_key_id: str = None, secret_key: str = None, base_url: str = None, style: str = "realistic", size: str = "512x512") -> Dict[str, Any]:
        """基于场景生成图像
        
        Args:
            scene: 场景信息
            access_key_id: 火山引擎/即梦API的Access Key ID
            secret_key: 火山引擎/即梦API的Secret Access Key
            base_url: 图像生成API基础URL
            style: 图像风格，支持：realistic, anime, painting, sketch, 3d
            size: 图像尺寸，例如 "512x512"
            
        Returns:
            Dict[str, Any]: 图像信息
        """
        try:
            from agent.services.image_service import ImageService
            
            # 提取场景描述
            narrative = scene.get('narrative', '')
            key_elements = scene.get('key_elements', [])
            emotion_state = scene.get('emotion_state', {})
            
            # 构建更丰富的场景描述
            # 1. 从叙述中提取主要内容
            scene_description = narrative[:300]  # 截取前300个字符作为主要描述
            
            # 2. 添加关键元素
            if key_elements:
                elements_text = "，".join(key_elements[:3])
                scene_description += f"。场景中包含：{elements_text}"
            
            # 3. 添加情感状态描述，让图像更有情感表现
            if isinstance(emotion_state, dict) and emotion_state:
                emotions = []
                for character, emotion in emotion_state.items():
                    emotions.append(f"{character}：{emotion}")
                if emotions:
                    scene_description += f"。情感氛围：{'，'.join(emotions[:2])}"
            elif isinstance(emotion_state, str):
                scene_description += f"。情感氛围：{emotion_state}"
            
            # 创建图像服务
            image_service = ImageService(access_key_id, secret_key, base_url)
            
            # 生成图像，传递用户选择的风格和尺寸
            result = image_service.generate_image(
                prompt=scene_description,
                style=style,
                size=size
            )
            
            # 返回结果
            return {
                "status": "success",
                "image_url": result.get('image_url'),
                "remote_url": result.get('remote_url', ''),
                "prompt": result.get('prompt', scene_description)
            }
        except Exception as e:
            logger.exception(f"生成图像失败: {str(e)}")
            return {
                "status": "error",
                "message": f"生成图像失败: {str(e)}"
            }
    
    def _search_story_info(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """搜索故事信息
        
        Args:
            context: 上下文信息，包括：
                - query: 搜索查询
                
        Returns:
            Dict[str, Any]: 搜索结果
        """
        query = context.get('query', '')
        
        if not query:
            return {
                "status": "error",
                "message": "搜索查询不能为空"
            }
            
        if not self.document_id or not self.character_name:
            return {
                "status": "error",
                "message": "请先开始交互"
            }
            
        # 收集所有可搜索的信息
        search_corpus = []
        
        # 添加记忆库内容
        for memory in self.memory_store:
            search_corpus.append({
                'content': memory['content'],
                'source': f"记忆 (第{memory['chapter']}章)",
                'type': 'memory',
                'importance': memory.get('importance', 3)
            })
            
        # 添加章节摘要
        for i, summary in enumerate(self.chapter_summaries):
            if isinstance(summary, dict) and 'summary' in summary:
                search_corpus.append({
                    'content': summary['summary'],
                    'source': f"章节摘要 (第{i+1}章)",
                    'type': 'summary',
                    'importance': 4
                })
            
        # 添加角色信息
        if self.character_name in self.characters:
            char_info = self.characters[self.character_name]
            search_corpus.append({
                'content': f"{self.character_name}: {char_info.get('description', '')}",
                'source': "角色信息",
                'type': 'character',
                'importance': 5
            })
            
        # 添加之前的交互历史
        for item in self.interaction_history:
            if item.get('type') == 'scene':
                scene = item.get('content', {})
                narrative = scene.get('narrative', '')
                if narrative:
                    search_corpus.append({
                        'content': narrative,
                        'source': f"场景 (ID: {scene.get('interaction_id', 'unknown')})",
                        'type': 'scene',
                        'importance': 2
                    })
        
        # 简单的相关性评分（实际实现可以使用更复杂的语义搜索）
        results = []
        query_terms = query.lower().split()
        
        for item in search_corpus:
            content = item['content'].lower()
            score = 0
            
            # 计算简单的相关性得分
            for term in query_terms:
                if term in content:
                    score += content.count(term)
            
            # 考虑重要性
            score *= item.get('importance', 1)
            
            if score > 0:
                results.append({
                    'content': item['content'],
                    'source': item['source'],
                    'type': item['type'],
                    'relevance': score
                })
        
        # 按相关性排序
        results = sorted(results, key=lambda x: x['relevance'], reverse=True)
        
        # 限制结果数量
        top_results = results[:10] if len(results) > 10 else results
        
        return {
            "status": "success",
            "message": f"找到 {len(top_results)} 条相关信息",
            "results": top_results,
            "character_name": self.character_name,
            "query": query
        }
    
    def _get_related_memories(self, query: str) -> List[Dict[str, Any]]:
        """获取与查询相关的记忆
        
        Args:
            query: 用户输入或查询字符串
            
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
            
            # 考虑章节相关性：当前章节和相邻章节的记忆更重要
            memory_chapter = memory.get('chapter', 0)
            if memory_chapter == self.current_chapter:
                score *= 1.5
            elif memory_chapter == self.current_chapter - 1:
                score *= 1.2
                
            if score > 0:
                scored_memories.append((memory, score))
                
        # 按评分排序并取前10条
        if not scored_memories:
            # 如果没有相关记忆，返回最重要的几条记忆
            important_memories = sorted(self.memory_store, key=lambda x: x.get('importance', 0), reverse=True)
            return important_memories[:5]
            
        sorted_memories = [m[0] for m in sorted(scored_memories, key=lambda x: x[1], reverse=True)]
        return sorted_memories[:10]
    
    def _detect_document_language(self, document_id: str) -> str:
        """根据文档ID检测语言，目前支持的前缀：en-(英文), zh-(中文)
        默认为中文"""
        if document_id.startswith('en-'):
            return 'english'
        elif document_id.startswith('zh-'):
            return 'chinese'
        else:
            # 默认中文
            return 'chinese' 
    
    def _determine_image_style(self, scene: Dict[str, Any]) -> str:
        """使用LLM分析场景，确定最适合的图像风格
        
        Args:
            scene: 场景信息
            
        Returns:
            str: 推荐的图像风格，可能为："realistic", "anime", "painting", "sketch", "3d"
        """
        try:
            # 提取场景描述和关键元素
            narrative = scene.get('narrative', '')
            key_elements = scene.get('key_elements', [])
            emotion_state = scene.get('emotion_state', {})
            
            # 提取情感状态文本
            emotion_text = ""
            if isinstance(emotion_state, dict):
                emotion_text = ", ".join([f"{k}: {v}" for k, v in emotion_state.items()])
            else:
                emotion_text = str(emotion_state)
            
            # 构建提示
            prompt = f"""你是一位专业的视觉艺术指导，需要为以下场景选择最合适的视觉风格。请基于场景描述、人物情感和关键元素，选择最适合的图像风格。

### 场景描述
{narrative[:300]}

### 情感状态
{emotion_text}

### 关键元素
{', '.join(key_elements) if key_elements else "无"}

### 文档语言和语境
- 文档ID: {self.document_id}
- 语言: {self.document_language}
- 当前章节: {self.current_chapter}

请分析这个场景的氛围、情绪、和内容，然后从以下选项中选择一种最适合的图像风格：
1. realistic - 写实风格，适合真实场景、人物肖像、自然风景等
2. anime - 动漫风格，适合可爱、轻松、活泼的场景或角色
3. painting - 绘画风格，适合梦幻、艺术、抽象或富有想象力的场景
4. sketch - 素描风格，适合紧张、黑暗、情感强烈或戏剧性场景
5. 3d - 3D渲染风格，适合未来场景、科技元素、或需要特殊视觉效果的场景

只回答一个单词作为风格选择："realistic", "anime", "painting", "sketch", 或 "3d"。"""

            # 调用LLM确定风格
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.1,
                max_tokens=20
            )
            
            content = response.choices[0].message.content.strip().lower()
            
            # 提取风格关键词
            valid_styles = ["realistic", "anime", "painting", "sketch", "3d"]
            
            # 如果结果直接匹配有效风格，则返回
            for style in valid_styles:
                if style in content:
                    logger.info(f"LLM推荐的图像风格: {style}")
                    return style
            
            # 如果没有明确匹配，尝试查找替代词
            style_map = {
                "写实": "realistic", "逼真": "realistic", "真实": "realistic", "photorealistic": "realistic", "real": "realistic",
                "动漫": "anime", "卡通": "anime", "cartoon": "anime", "萌": "anime", "可爱": "anime", "cute": "anime",
                "绘画": "painting", "艺术": "painting", "水彩": "painting", "油画": "painting", "art": "painting", "dream": "painting",
                "素描": "sketch", "铅笔": "sketch", "黑白": "sketch", "线条": "sketch", "速写": "sketch", "pencil": "sketch",
                "3d": "3d", "三维": "3d", "渲染": "3d", "立体": "3d", "科技": "3d", "未来": "3d", "render": "3d"
            }
            
            for term, style in style_map.items():
                if term in content:
                    logger.info(f"LLM提及相关词'{term}'，选择图像风格: {style}")
                    return style
            
            # 默认返回写实风格
            logger.info("无法确定明确风格，默认使用写实风格")
            return "realistic"
            
        except Exception as e:
            logger.error(f"确定图像风格时出错: {str(e)}")
            return "realistic"  # 出错时默认使用写实风格
    
    def _auto_generate_image(self, scene: Dict[str, Any], access_key_id: str, secret_key: str, base_url: str = None) -> Dict[str, Any]:
        """自动为场景生成图像
        
        Args:
            scene: 场景信息
            access_key_id: API访问密钥ID
            secret_key: API密钥
            base_url: API基础URL
            
        Returns:
            Dict[str, Any]: 图像生成结果
        """
        if not access_key_id or not secret_key:
            logger.warning("未设置图像生成API密钥，无法自动生成图像")
            return {
                "status": "error",
                "message": "未设置图像生成API密钥"
            }
            
        # 判断场景是否适合生成图像
        if not self._evaluate_scene_for_image(scene):
            logger.info("当前场景不适合生成图像，跳过自动生成")
            return {
                "status": "skipped",
                "message": "当前场景不适合生成图像"
            }
            
        # 适合生成图像，调用图像生成方法
        logger.info("当前场景适合生成图像，开始自动生成...")
        try:
            # 使用LLM确定最适合的图像风格
            style = self._determine_image_style(scene)
            logger.info(f"为场景选择的图像风格: {style}")
            
            # 生成图像
            return self.generate_image_from_scene(
                scene,
                access_key_id=access_key_id,
                secret_key=secret_key,
                base_url=base_url,
                style=style,
                size="512x512"
            )
        except Exception as e:
            logger.exception(f"自动生成图像失败: {str(e)}")
            return {
                "status": "error",
                "message": f"自动生成图像失败: {str(e)}"
            }