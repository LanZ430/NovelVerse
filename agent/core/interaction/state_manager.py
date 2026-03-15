"""状态管理器模块，负责管理交互状态

该模块负责管理交互状态的保存和加载，记录用户选择、偏离和交互历史。
"""

from typing import Dict, Any, List, Optional
import logging
import json
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class StateManager:
    """状态管理器，负责管理交互状态的保存和加载"""
    
    def __init__(self, data_dir: str = './data'):
        """初始化状态管理器
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.interactions_dir = self.data_dir / 'interactions'
        self.interactions_dir.mkdir(parents=True, exist_ok=True)
        
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
    
    def set_interaction_context(self, document_id: str, character_name: str, chapter: int) -> None:
        """设置交互上下文
        
        Args:
            document_id: 文档ID
            character_name: 角色名称
            chapter: 章节编号
        """
        self.document_id = document_id
        self.character_name = character_name
        self.current_chapter = chapter
        
        # 初始化状态文件路径
        self.state_file = self.interactions_dir / f"{document_id}_{character_name}_chapter_{chapter}_state.json"
        
        # 尝试加载现有状态
        if self.state_file.exists():
            self.load_interaction_state()
        else:
            # 初始化新的交互状态
            self.interaction_history = []
            self.current_state = {
                'progress': 0,
                'choices': [],
                'divergences': []
            }
            self.save_interaction_state()
    
    def load_interaction_state(self) -> None:
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
                # 加载其他状态数据
                self.document_id = state_data.get('document_id', self.document_id)
                self.character_name = state_data.get('character_name', self.character_name)
                self.current_chapter = state_data.get('chapter', self.current_chapter)
            
            logger.info(f"已加载交互状态: {self.state_file}")
        except Exception as e:
            logger.error(f"加载交互状态失败: {str(e)}")
    
    def save_interaction_state(self) -> None:
        """保存交互状态"""
        if not self.state_file:
            if not (self.document_id and self.character_name and self.current_chapter):
                logger.warning("保存状态失败: 未设置交互上下文")
                return
                
            self.state_file = self.interactions_dir / f"{self.document_id}_{self.character_name}_chapter_{self.current_chapter}_state.json"
            
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
                'current_state': self.current_state
            }
            
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"已保存交互状态: {self.state_file}")
        except Exception as e:
            logger.error(f"保存交互状态失败: {str(e)}")
    
    def add_scene_to_history(self, scene: Dict[str, Any]) -> None:
        """添加场景到历史记录
        
        Args:
            scene: 场景信息
        """
        self.interaction_history.append({
            'timestamp': self._get_current_timestamp(),
            'type': 'scene',
            'content': scene
        })
        self.save_interaction_state()
    
    def add_user_input_to_history(self, user_input: str, evaluation: Dict[str, Any] = None) -> None:
        """添加用户输入和评估结果到历史记录
        
        Args:
            user_input: 用户输入
            evaluation: 评估结果
        """
        self.interaction_history.append({
            'timestamp': self._get_current_timestamp(),
            'type': 'user_input',
            'content': user_input,
            'evaluation': evaluation
        })
        
        # 如果有评估结果，更新状态
        if evaluation:
            # 更新进度
            if 'progress' in evaluation:
                self.current_state['progress'] = evaluation['progress']
                
            # 记录选择
            self.current_state['choices'].append({
                'timestamp': self._get_current_timestamp(),
                'content': user_input,
                'evaluation': evaluation
            })
            
            # 检查是否存在重大偏离
            divergence_level = evaluation.get('divergence', {}).get('level', 0)
            if divergence_level > 0:
                self.current_state['divergences'].append({
                    'timestamp': self._get_current_timestamp(),
                    'description': evaluation.get('divergence', {}).get('description', ''),
                    'level': divergence_level
                })
        
        self.save_interaction_state()
    
    def add_deviated_ending_to_history(self, scene: Dict[str, Any]) -> None:
        """添加偏离结局到历史记录
        
        Args:
            scene: 偏离结局场景
        """
        self.interaction_history.append({
            'timestamp': self._get_current_timestamp(),
            'type': 'scene',
            'content': scene,
            'is_deviated_ending': True
        })
        
        # 更新状态
        self.current_state['progress'] = 100
        
        self.save_interaction_state()
    
    def get_last_scene(self) -> Optional[Dict[str, Any]]:
        """获取最后一个场景
        
        Returns:
            Optional[Dict[str, Any]]: 最后一个场景
        """
        for item in reversed(self.interaction_history):
            if item.get('type') == 'scene':
                return item.get('content')
        return None
    
    def get_recent_choices(self, max_items: int = 3) -> List[Dict[str, Any]]:
        """获取最近的选择
        
        Args:
            max_items: 最大项数
            
        Returns:
            List[Dict[str, Any]]: 最近的选择
        """
        choices = self.current_state.get('choices', [])
        return choices[-max_items:] if choices else []
    
    def get_recent_divergences(self, max_items: int = 2) -> List[Dict[str, Any]]:
        """获取最近的偏离
        
        Args:
            max_items: 最大项数
            
        Returns:
            List[Dict[str, Any]]: 最近的偏离
        """
        divergences = self.current_state.get('divergences', [])
        return divergences[-max_items:] if divergences else []
    
    def get_current_progress(self) -> int:
        """获取当前进度
        
        Returns:
            int: 当前进度
        """
        return self.current_state.get('progress', 0)
    
    def get_scenes_in_history(self) -> List[Dict[str, Any]]:
        """获取历史记录中的所有场景
        
        Returns:
            List[Dict[str, Any]]: 场景列表
        """
        return [item.get('content', {}) for item in self.interaction_history if item.get('type') == 'scene']
    
    def transition_to_new_chapter(self, new_chapter: int) -> None:
        """过渡到新章节
        
        Args:
            new_chapter: 新章节编号
        """
        # 保存当前章节状态
        self.save_interaction_state()
        
        # 更新章节
        self.current_chapter = new_chapter
        
        # 更新状态文件路径
        self.state_file = self.interactions_dir / f"{self.document_id}_{self.character_name}_chapter_{new_chapter}_state.json"
        
        # 如果新章节状态文件存在，加载状态，否则初始化新状态
        if self.state_file.exists():
            self.load_interaction_state()
        else:
            # 初始化新的交互状态
            self.interaction_history = []
            self.current_state = {
                'progress': 0,
                'choices': [],
                'divergences': []
            }
            self.save_interaction_state()
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳
        
        Returns:
            str: 时间戳字符串
        """
        import datetime
        return datetime.datetime.now().isoformat() 