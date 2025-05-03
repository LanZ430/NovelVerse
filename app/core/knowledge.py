from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import faiss
import numpy as np
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
import itertools
import re
from config.config import settings

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class KnowledgeItem:
    content: str
    metadata: Dict
    embedding: Optional[np.ndarray] = None
    item_type: str = "general"  # 可以是 character, location, event, item 等
    timestamp: str = datetime.now().isoformat()
    importance: int = 1  # 1-5的重要性评分

@dataclass
class Character:
    name: str
    description: str
    relationships: List[Dict[str, str]]  # [{"target": "角色名", "relation": "关系描述"}]
    appearances: List[int]  # 出现的章节号
    development: List[Dict[str, str]]  # [{"chapter": 章节号, "change": "变化描述"}]
    traits: Set[str]  # 性格特征
    emotions: Dict[int, str]  # {章节号: "情感状态"}

@dataclass
class Location:
    name: str
    description: str
    atmosphere: str
    events: List[Dict[str, any]]  # 在此地点发生的事件
    characters: Set[str]  # 出现过的角色

@dataclass
class Event:
    description: str
    chapter: int
    importance: int
    characters: List[str]
    location: str
    time_context: str
    consequences: List[str]
    branches: List[str]

class KnowledgeBase:
    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.vector_store_path = settings.VECTOR_DIR / novel_id
        self.metadata_path = settings.DATA_DIR / 'metadata' / f"{novel_id}_knowledge.json"
        self.index: Optional[faiss.Index] = None
        self.items: List[KnowledgeItem] = []
        self.characters: Dict[str, Character] = {}
        self.locations: Dict[str, Location] = {}
        self.events: List[Event] = []
        self.time_markers: Dict[int, List[str]] = {}  # {章节号: [时间标记]}
        self.chapter_progress: Dict[str, Dict] = {}  # 新增：章节进度追踪
        self.chapter_summaries: Dict[int, str] = {}  # 新增：章节摘要
        
    def initialize(self) -> None:
        """初始化或加载知识库"""
        if self.vector_store_path.exists() and self.metadata_path.exists():
            self._load_existing_store()
        else:
            self._create_new_store()
            
    def _load_existing_store(self) -> None:
        """加载已存在的向量存储和元数据"""
        try:
            # 加载向量索引
            self.index = faiss.read_index(str(self.vector_store_path / "vectors.index"))
            
            # 加载元数据
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                
            # 恢复知识项
            self.items = [KnowledgeItem(**item) for item in metadata['items']]
            
            # 恢复角色信息
            self.characters = {
                name: Character(**data) 
                for name, data in metadata['characters'].items()
            }
            
            # 恢复地点信息
            self.locations = {
                name: Location(**data)
                for name, data in metadata['locations'].items()
            }
            
            # 恢复事件信息
            self.events = [Event(**event) for event in metadata['events']]
            
            # 恢复时间标记
            self.time_markers = metadata['time_markers']
            
            # 恢复章节进度
            self.chapter_progress = metadata['chapter_progress']
            
            # 恢复章节摘要
            self.chapter_summaries = metadata.get('chapter_summaries', {})
            
            logger.info(f"Successfully loaded knowledge base for novel {self.novel_id}")
            
        except Exception as e:
            logger.error(f"Error loading knowledge base: {str(e)}")
            self._create_new_store()
        
    def _create_new_store(self) -> None:
        """创建新的向量存储"""
        # 创建向量索引
        dimension = 768  # 使用默认的向量维度
        self.index = faiss.IndexFlatL2(dimension)
        
        # 创建必要的目录
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化空的知识库
        self.save()
        logger.info(f"Created new knowledge base for novel {self.novel_id}")
        
    def add_chapter_knowledge(self, chapter_number: int, metadata: Dict) -> None:
        """添加章节相关的知识"""
        try:
            # 1. 更新角色信息
            self._update_characters(chapter_number, metadata['characters'])
            
            # 2. 更新地点信息
            self._update_locations(chapter_number, metadata['locations'])
            
            # 3. 更新事件信息
            self._update_events(chapter_number, metadata['events'])
            
            # 4. 提取和更新时间标记
            self._update_time_markers(chapter_number, metadata.get('time_markers', []))
            
            # 5. 保存更新后的知识库
            self.save()
            
            logger.info(f"Successfully added knowledge for chapter {chapter_number}")
            
        except Exception as e:
            logger.error(f"Error adding chapter knowledge: {str(e)}")
            raise
            
    def _update_characters(self, chapter_number: int, characters_data: List[Dict]) -> None:
        """更新角色信息"""
        for char_data in characters_data:
            name = char_data['name']
            if name not in self.characters:
                self.characters[name] = Character(
                    name=name,
                    description=char_data['description'],
                    relationships=[],
                    appearances=[chapter_number],
                    development=[],
                    traits=set(),
                    emotions={}
                )
            
            char = self.characters[name]
            # 更新出场信息
            if chapter_number not in char.appearances:
                char.appearances.append(chapter_number)
            
            # 更新关系
            for rel in char_data.get('relationships', []):
                if isinstance(rel, str):
                    relation = {"target": "unknown", "relation": rel}
                else:
                    relation = rel
                if relation not in char.relationships:
                    char.relationships.append(relation)
            
            # 更新性格发展
            if char_data.get('development'):
                char.development.append({
                    "chapter": chapter_number,
                    "change": char_data['development']
                })
            
            # 更新特征
            if char_data.get('traits'):
                char.traits.update(char_data['traits'])
            
            # 更新情感状态
            if char_data.get('emotion'):
                char.emotions[chapter_number] = char_data['emotion']
                
    def _update_locations(self, chapter_number: int, locations_data: List[Dict]) -> None:
        """更新地点信息"""
        for loc_data in locations_data:
            name = loc_data['name']
            if name not in self.locations:
                self.locations[name] = Location(
                    name=name,
                    description=loc_data['description'],
                    atmosphere=loc_data.get('atmosphere', ''),
                    events=[],
                    characters=set()
                )
            
            loc = self.locations[name]
            # 更新描述和氛围
            if loc_data.get('description') and loc_data['description'] not in loc.description:
                loc.description += f"; {loc_data['description']}"
            if loc_data.get('atmosphere') and loc_data['atmosphere'] not in loc.atmosphere:
                loc.atmosphere += f"; {loc_data['atmosphere']}"
                
    def _update_events(self, chapter_number: int, events_data: List[Dict]) -> None:
        """更新事件信息"""
        for event_data in events_data:
            event = Event(
                description=event_data['description'],
                chapter=chapter_number,
                importance=event_data.get('importance', 3),
                characters=event_data.get('characters', []),
                location=event_data.get('location', '未知'),
                time_context=event_data.get('time_context', ''),
                consequences=event_data.get('consequences', []),
                branches=event_data.get('branches', [])
            )
            self.events.append(event)
            
            # 更新相关地点的事件记录
            if event.location in self.locations:
                self.locations[event.location].events.append({
                    'description': event.description,
                    'chapter': chapter_number
                })
                
            # 更新相关角色的出场记录
            for char_name in event.characters:
                if char_name in self.locations:
                    self.locations[event.location].characters.add(char_name)
                    
    def _update_time_markers(self, chapter_number: int, markers: List[str]) -> None:
        """更新时间标记"""
        if markers:
            self.time_markers[chapter_number] = markers
            
    def get_character_context(self, character_name: str, current_chapter: int) -> Dict:
        """获取角色的上下文信息"""
        if character_name not in self.characters:
            return {}
            
        char = self.characters[character_name]
        
        # 获取章节概括
        chapter_summary = ""
        summary_path = settings.DATA_DIR / 'summaries' / f"summary_{current_chapter:03d}.txt"
        try:
            if summary_path.exists():
                with open(summary_path, 'r', encoding='utf-8') as f:
                    chapter_summary = f.read().strip()
        except Exception as e:
            logger.error(f"Error reading chapter summary: {str(e)}")
        
        # 获取角色的历史发展
        development_history = []
        for dev in char.development:
            if dev['chapter'] <= current_chapter:
                development_history.append(dev)
                
        # 获取角色的情感变化
        emotions_history = {
            chapter: emotion 
            for chapter, emotion in char.emotions.items() 
            if chapter <= current_chapter
        }
        
        # 获取角色参与的事件
        related_events = [
            asdict(event) 
            for event in self.events 
            if character_name in event.characters and event.chapter <= current_chapter
        ]
        
        return {
            'basic_info': {
                'name': char.name,
                'description': char.description,
                'traits': list(char.traits)
            },
            'relationships': char.relationships,
            'development_history': development_history,
            'emotions_history': emotions_history,
            'related_events': related_events,
            'appearances': [ch for ch in char.appearances if ch <= current_chapter],
            'summary': chapter_summary  # 添加章节概括
        }
        
    def get_location_context(self, location_name: str, current_chapter: int) -> Dict:
        """获取地点的上下文信息"""
        if location_name not in self.locations:
            return {}
            
        loc = self.locations[location_name]
        
        # 获取在此地点发生的事件
        location_events = [
            event for event in loc.events 
            if event['chapter'] <= current_chapter
        ]
        
        return {
            'basic_info': {
                'name': loc.name,
                'description': loc.description,
                'atmosphere': loc.atmosphere
            },
            'events': location_events,
            'characters': list(loc.characters)
        }
        
    def get_timeline(self, start_chapter: int, end_chapter: int) -> List[Dict]:
        """获取指定章节范围的时间线"""
        timeline = []
        
        # 添加事件
        for event in self.events:
            if start_chapter <= event.chapter <= end_chapter:
                timeline.append({
                    'type': 'event',
                    'chapter': event.chapter,
                    'description': event.description,
                    'importance': event.importance,
                    'time_context': event.time_context
                })
        
        # 添加时间标记
        for chapter, markers in self.time_markers.items():
            if start_chapter <= chapter <= end_chapter:
                for marker in markers:
                    timeline.append({
                        'type': 'time_marker',
                        'chapter': chapter,
                        'description': marker
                    })
        
        # 按章节号和重要性排序
        return sorted(timeline, key=lambda x: (x['chapter'], -x.get('importance', 0)))
        
    def update_chapter_progress(self, chapter: int, progress_info: Dict) -> None:
        """更新章节进度信息"""
        chapter_key = str(chapter)
        if chapter_key not in self.chapter_progress:
            self.chapter_progress[chapter_key] = {
                'completed_plot_points': [],
                'current_scene': '章节开始',
                'progress_percentage': 0
            }
        
        self.chapter_progress[chapter_key].update({
            'completed_plot_points': progress_info.get('completed_plot_points', []),
            'current_scene': progress_info.get('current_scene', ''),
            'progress_percentage': progress_info.get('progress_percentage', 0)
        })
        
        # 保存更新后的知识库
        self.save()
        
    def get_chapter_progress(self, chapter: int) -> Dict:
        """获取章节进度信息"""
        chapter_key = str(chapter)
        return self.chapter_progress.get(chapter_key, {
            'completed_plot_points': [],
            'current_scene': '章节开始',
            'progress_percentage': 0
        })
        
    def save(self) -> None:
        """保存知识库到磁盘"""
        try:
            # 保存向量索引
            faiss.write_index(self.index, str(self.vector_store_path / "vectors.index"))
            
            # 准备元数据
            metadata = {
                'items': [asdict(item) for item in self.items],
                'characters': {name: asdict(char) for name, char in self.characters.items()},
                'locations': {name: asdict(loc) for name, loc in self.locations.items()},
                'events': [asdict(event) for event in self.events],
                'time_markers': self.time_markers,
                'chapter_progress': self.chapter_progress,
                'chapter_summaries': self.chapter_summaries,
                'last_updated': datetime.now().isoformat()
            }
            
            # 转换 set 为 list
            for char in metadata['characters'].values():
                if 'traits' in char and isinstance(char['traits'], set):
                    char['traits'] = list(char['traits'])
                    
            for loc in metadata['locations'].values():
                if 'characters' in loc and isinstance(loc['characters'], set):
                    loc['characters'] = list(loc['characters'])
            
            # 保存元数据
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Successfully saved knowledge base for novel {self.novel_id}")
            
        except Exception as e:
            logger.error(f"Error saving knowledge base: {str(e)}")
            raise

    def add_chapter_summary(self, chapter_number: int, summary: str) -> None:
        """添加或更新章节摘要"""
        try:
            self.chapter_summaries[chapter_number] = summary
            logger.info(f"Added summary for chapter {chapter_number}")
        except Exception as e:
            logger.error(f"Error adding chapter summary: {str(e)}")
    
    def get_chapter_summary(self, chapter_number: int) -> str:
        """获取章节摘要"""
        return self.chapter_summaries.get(chapter_number, "")

class StoryContext:
    """故事上下文管理器"""
    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base
        self.current_context: Dict = {
            'chapter': None,
            'scene': None,
            'characters': [],
            'location': None,
            'time': None,
            'events': []
        }
        self.context_history: List[Dict] = []
        
    def update_context(self, **kwargs) -> None:
        """更新当前上下文"""
        # 保存当前上下文到历史
        self.context_history.append(self.current_context.copy())
        
        # 更新上下文
        for key, value in kwargs.items():
            if key in self.current_context:
                self.current_context[key] = value
                
        # 如果更新了章节，自动更新相关信息
        if 'chapter' in kwargs:
            self._update_chapter_context(kwargs['chapter'])
                
    def _update_chapter_context(self, chapter_number: int) -> None:
        """更新章节相关的上下文信息"""
        # 获取章节中的事件
        chapter_events = [
            event for event in self.knowledge_base.events 
            if event.chapter == chapter_number
        ]
        
        # 更新事件列表
        self.current_context['events'] = [asdict(event) for event in chapter_events]
        
        # 更新时间标记
        if chapter_number in self.knowledge_base.time_markers:
            self.current_context['time'] = self.knowledge_base.time_markers[chapter_number]
        
        # 更新出场角色
        characters = set()
        for event in chapter_events:
            characters.update(event.characters)
        self.current_context['characters'] = list(characters)
                
    def get_relevant_knowledge(self, query: str, top_k: int = 3) -> List[Dict]:
        """获取与当前上下文相关的知识"""
        relevant_knowledge = []
        
        # 1. 获取当前角色的上下文
        for char_name in self.current_context['characters']:
            char_context = self.knowledge_base.get_character_context(
                char_name, 
                self.current_context['chapter']
            )
            if char_context:
                relevant_knowledge.append({
                    'type': 'character',
                    'content': char_context
                })
                
        # 2. 获取当前地点的上下文
        if self.current_context['location']:
            loc_context = self.knowledge_base.get_location_context(
                self.current_context['location'],
                self.current_context['chapter']
            )
            if loc_context:
                relevant_knowledge.append({
                    'type': 'location',
                    'content': loc_context
                })
                
        # 3. 获取当前事件的上下文
        if self.current_context['events']:
            relevant_knowledge.append({
                'type': 'events',
                'content': self.current_context['events']
            })
            
        # 4. 获取时间线上下文
        timeline = self.knowledge_base.get_timeline(
            max(1, self.current_context['chapter'] - 2),
            self.current_context['chapter']
        )
        if timeline:
            relevant_knowledge.append({
                'type': 'timeline',
                'content': timeline
            })
            
        return relevant_knowledge[:top_k] 