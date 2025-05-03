"""
小说处理模块：负责小说文件的读取、章节分割、内容分析和知识库构建
"""

from typing import List, Dict, Any
from pathlib import Path
import regex as re
import json
import logging
import unicodedata
from datetime import datetime
from dataclasses import dataclass, asdict

import docx
import PyPDF2
from openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from config.config import settings

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class Chapter:
    """章节数据类"""
    number: int          # 章节序号
    title: str          # 章节标题
    content: str        # 章节内容
    summary: str = ""   # 章节摘要
    index: int = 0      # 章节索引

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

class NovelProcessor:
    """小说处理器：负责小说文件的读取、处理和知识库构建"""
    
    def __init__(self, file_path: Path):
        """初始化小说处理器
        
        Args:
            file_path: 小说文件路径
        """
        self.file_path = Path(file_path)
        self.chapters: List[Chapter] = []
        self.metadata: Dict[str, Any] = {}
        
        # 初始化必要的组件
        self._init_components()
    
    def _init_components(self) -> None:
        """初始化处理组件"""
        # 文本分割器（用于向量化）
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        
        # 向量嵌入模型
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2"
        )
    
        # API客户端
        try:
            if not settings.DEEPSEEK_API_KEY:
                raise ValueError("DeepSeek API key is not set. Please set DEEPSEEK_API_KEY in your .env file.")
            
            self.client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com"
            )
            
            # 测试API连接
            try:
                test_response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Test connection"}
                    ],
                    stream=False
                )
                if test_response.choices[0].message.content:
                    logger.info("DeepSeek API 连接测试成功")
                else:
                    raise Exception("API响应内容为空")
            except Exception as e:
                logger.error(f"DeepSeek API 连接测试失败: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"DeepSeek API 初始化失败: {str(e)}")
            raise
    
    def process_novel(self) -> None:
        """处理小说文件的主流程"""
        try:
            # 1. 读取和清理文本
            content = self._read_and_clean_file()
            
            # 2. 分割章节
            self._split_into_chapters(content)
            if not self.chapters:
                raise ValueError("未能正确分割章节")
            
            # 3. 分析章节内容
            self._process_all_chapters()
            
            # 4. 创建向量存储
            self._create_vector_store()
            
            # 5. 保存处理结果
            self._save_results()
            
        except Exception as e:
            logger.error(f"处理小说文件时出错: {str(e)}")
            raise
    
    def _read_and_clean_file(self) -> str:
        """读取并清理文件内容"""
        content = self._read_file()
        return self._clean_text(content)
    
    def _read_file(self) -> str:
        """根据文件类型读取内容"""
        readers = {
            '.txt': self._read_text,
            '.pdf': self._read_pdf,
            '.doc': self._read_word,
            '.docx': self._read_word
        }
        
        file_extension = self.file_path.suffix.lower()
        reader = readers.get(file_extension)
        
        if not reader:
            raise ValueError(f"不支持的文件格式: {file_extension}")
        
        return reader()
    
    def _read_text(self) -> str:
        """读取文本文件"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return f.read()
        
    def _read_pdf(self) -> str:
        """读取PDF文件"""
        with open(self.file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            return '\n'.join(page.extract_text() for page in pdf_reader.pages)
    
    def _read_word(self) -> str:
        """读取Word文件"""
        doc = docx.Document(self.file_path)
        return '\n'.join(paragraph.text for paragraph in doc.paragraphs)
    
    def _clean_text(self, text: str) -> str:
        """清理和规范化文本"""
        # 1. Unicode标准化
        text = unicodedata.normalize('NFKC', text)
        
        # 2. 统一标点符号
        text = re.sub(r'[""]', '"', text)
        text = re.sub(r'[\'\']', "'", text)
        
        # 3. 清理空白字符，但保留章节标记周围的空行
        # 先标记章节位置
        chapter_markers = re.finditer(r'\n\s*[IVXLC]+\s*\n', text)
        chapter_positions = [(m.start(), m.end()) for m in chapter_markers]
        
        # 分段处理文本
        cleaned_text = []
        last_end = 0
        
        for start, end in chapter_positions:
            # 处理章节前的文本
            before_chapter = text[last_end:start]
            before_chapter = re.sub(r'\s+', ' ', before_chapter)
            before_chapter = re.sub(r'\n{2,}', '\n\n', before_chapter)
            cleaned_text.append(before_chapter)
            
            # 保留章节标记及其周围的空行
            chapter_marker = text[start:end]
            cleaned_text.append(chapter_marker)
            
            last_end = end
        
        # 处理最后一段
        if last_end < len(text):
            remaining = text[last_end:]
            remaining = re.sub(r'\s+', ' ', remaining)
            remaining = re.sub(r'\n{2,}', '\n\n', remaining)
            cleaned_text.append(remaining)
        
        return ''.join(cleaned_text).strip()
    
    def _detect_chapter_pattern(self, content: str) -> str:
        """检测章节标记模式"""
        patterns = {
            'roman_centered': r'\n\s*[IVXLC]+\s*\n',  # 居中的罗马数字
            'roman_regular': r'\n[IVXLC]+\n',         # 普通的罗马数字
            'chinese_num': r'第[一二三四五六七八九十百千]+章',
            'chinese_digit': r'第\d+章',
            'english_lower': r'chapter \d+',
            'english_upper': r'CHAPTER \d+',
            'mixed': r'第.+章.*\n',
            'simple_roman': r'[IVXLC]+[\.\、]',
            'number_dot': r'\d+[\.\、]',
            'chinese_dot': r'[一二三四五六七八九十]+[\.\、]',
            'star_line': r'\*{3,}.*\*{3,}',
            'dash_line': r'-{3,}.*-{3,}'
        }
        
        # 统计每种模式的匹配次数
        pattern_counts = {}
        for name, pattern in patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            pattern_counts[name] = len(matches)
            logger.info(f"Pattern '{name}' found {len(matches)} matches")
        
        # 选择最匹配的模式
        best_pattern = max(pattern_counts.items(), key=lambda x: x[1])[0]
        logger.info(f"Selected best pattern: {best_pattern} with {pattern_counts[best_pattern]} matches")
        
        if pattern_counts[best_pattern] == 0:
            logger.warning("No chapter patterns found in content")
            # 如果没有找到任何模式，使用一个通用的模式
            return r'\n\s*[IVXLC]+\s*\n'
            
        return patterns[best_pattern]
    
    def _split_into_chapters(self, content: str) -> None:
        """将内容分割为章节"""
        logger.info("Starting chapter splitting...")
        
        # 1. 检测章节模式
        chapter_pattern = self._detect_chapter_pattern(content)
        logger.info(f"Using chapter pattern: {chapter_pattern}")
        
        # 2. 分割内容
        chapter_splits = re.split(f'({chapter_pattern})', content)
        logger.info(f"Found {len(chapter_splits)} potential chapter splits")
        
        # 3. 处理分割结果
        current_chapter = None
        current_content = []
        chapter_number = 0
        
        for i, split in enumerate(chapter_splits):
            if not split.strip():
                continue
            
            if re.search(chapter_pattern, split):
                if current_chapter:
                    self._add_chapter(chapter_number, current_chapter.strip(), current_content)
                    logger.info(f"Added chapter {chapter_number}: {current_chapter}")
                current_chapter = split.strip()
                current_content = []
                chapter_number += 1
            else:
                current_content.append(split.strip())
        
        # 处理最后一章
        if current_chapter:
            self._add_chapter(chapter_number, current_chapter.strip(), current_content)
            logger.info(f"Added final chapter {chapter_number}: {current_chapter}")
        
        if not self.chapters:
            logger.error("No chapters were found after splitting")
            raise ValueError("未能正确分割章节")
            
        logger.info(f"Successfully split content into {len(self.chapters)} chapters")
    
    def _add_chapter(self, number: int, title: str, content: List[str]) -> None:
        """添加新章节"""
        self.chapters.append(Chapter(
                number=number,
                title=title,
            content='\n'.join(content).strip(),
                index=number
            ))
        
    def _process_all_chapters(self) -> None:
        """处理所有章节内容"""
        for chapter in self.chapters:
            try:
                # 分析章节
                result = self._analyze_chapter(chapter)
                
                # 保存分析结果
                self._save_chapter_analysis(chapter, result)
                
                # 更新全局元数据
                self._update_global_metadata(result['metadata'])
                
            except Exception as e:
                logger.error(f"处理章节 {chapter.number} 时出错: {str(e)}")
                continue
    
    def _analyze_chapter(self, chapter: Chapter) -> Dict[str, Any]:
        """分析章节内容"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """你是一个专业的文学分析助手。请完成以下任务：
                    1. 生成章节内容摘要（200字以内）
                    2. 提取本章节关键信息：
                       - 人物：包括姓名、特征描述、关系、性格发展
                       - 场景：地点描述、环境特征、氛围营造
                       - 事件：重要情节、关键转折、可能的分支点
                       - 物品：重要道具、信物等
                       - 剧情：主要情节线索、伏笔、高潮点
                    3. 分析多视角叙述可能：
                       - 主角视角的体验重点
                       - 配角视角的独特观察
                       - 旁观者视角的整体把握
                    
                    请以JSON格式返回，不要包含任何Markdown标记：
                    {
                        "summary": "章节摘要",
                        "metadata": {
                            "characters": [
                                {
                                    "name": "名字",
                                    "description": "描述",
                                    "relationships": [],
                                    "development": "性格/身份的变化",
                                    "perspective": {
                                        "self": "自我视角的体验",
                                        "others": "他人眼中的形象"
                                    }
                                }
                            ],
                            "locations": [
                                {
                                    "name": "地点",
                                    "description": "描述",
                                    "atmosphere": "氛围特点"
                                }
                            ],
                            "events": [
                                {
                                    "description": "事件描述",
                                    "importance": "重要性评分1-5",
                                    "branches": ["可能的剧情分支"],
                                    "triggers": ["触发条件"]
                                }
                            ],
                            "items": [
                                {
                                    "name": "物品",
                                    "significance": "重要性说明",
                                    "effects": ["可能产生的影响"]
                                }
                            ],
                            "plot_points": [
                                {
                                    "type": "伏笔/高潮/转折",
                                    "description": "描述",
                                    "potential_developments": ["可能的发展方向"]
                                }
                            ]
                        }
                    }"""
                },
                {
                    "role": "user",
                    "content": f"""
                    章节标题: {chapter.title}
                    章节序号: {chapter.number}
                    
                    内容:
                    {chapter.content}
                    """
                }
            ]
            
            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=0.3,
                    stream=False
                )
                
                # 清理响应内容，移除可能的Markdown标记
                content = response.choices[0].message.content
                if content.startswith('```json'):
                    content = content[7:]  # 移除 ```json
                if content.endswith('```'):
                    content = content[:-3]  # 移除 ```
                content = content.strip()
                
                result = json.loads(content)
                logger.info(f"成功分析章节 {chapter.number}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"解析API响应JSON失败: {str(e)}")
                logger.error(f"原始响应内容: {response.choices[0].message.content}")
                return self._get_empty_analysis()
                
        except Exception as e:
            logger.error(f"调用API分析章节 {chapter.number} 时出错: {str(e)}")
            return self._get_empty_analysis()
    
    def _get_empty_analysis(self) -> Dict[str, Any]:
        """返回空的分析结果"""
        return {
            "summary": "",
            "metadata": {
                "characters": [],
                "locations": [],
                "events": [],
                "items": [],
                "plot_points": []
            }
        }
    
    def _save_chapter_analysis(self, chapter: Chapter, result: Dict[str, Any]) -> None:
        """保存章节分析结果"""
        base_dir = settings.NOVEL_DIR / self.file_path.stem
        
        # 保存摘要
        summary_dir = base_dir / 'summaries'
        summary_dir.mkdir(parents=True, exist_ok=True)
        with open(summary_dir / f'summary_{chapter.number:03d}.txt', 'w', encoding='utf-8') as f:
            f.write(result['summary'])
            
        # 保存元数据
        metadata_dir = base_dir / 'metadata'
        metadata_dir.mkdir(parents=True, exist_ok=True)
        with open(metadata_dir / f'metadata_{chapter.number:03d}.json', 'w', encoding='utf-8') as f:
            json.dump(result['metadata'], f, ensure_ascii=False, indent=2)
        
        # 更新章节对象
        chapter.summary = result['summary']
    
    def _update_global_metadata(self, chapter_metadata: Dict[str, Any]) -> None:
        """更新全局元数据"""
        if not self.metadata:
            self._init_global_metadata()
        
        # 更新人物信息
        for char in chapter_metadata["characters"]:
            self._update_character_info(char)
        
        # 更新地点信息
        for loc in chapter_metadata["locations"]:
            self._update_location_info(loc)
        
        # 更新事件信息
        self._update_event_info(chapter_metadata["events"])
        
        # 更新物品信息
        for item in chapter_metadata["items"]:
            self._update_item_info(item)
    
    def _update_character_info(self, char: Dict[str, Any]) -> None:
        """更新人物信息"""
        char_name = char["name"]
        if char_name not in self.metadata["world_knowledge_base"]["characters"]:
            self.metadata["world_knowledge_base"]["characters"][char_name] = {
                "description": char["description"],
                "first_appearance": f"Chapter {self.chapters[-1].number}",
                "appearances": [self.chapters[-1].number],
                "relationships": char.get("relationships", []),
                "development": char.get("development", ""),
                "perspective": char.get("perspective", {})
            }
        else:
            existing = self.metadata["world_knowledge_base"]["characters"][char_name]
            if self.chapters[-1].number not in existing["appearances"]:
                existing["appearances"].append(self.chapters[-1].number)
            if char["description"] not in existing["description"]:
                existing["description"] += f"; {char['description']}"
            existing["relationships"].extend(
                [r for r in char.get("relationships", []) if r not in existing["relationships"]]
            )
            if char["development"] not in existing["development"]:
                existing["development"] += f"; {char['development']}"
            existing["perspective"].update(char.get("perspective", {}))
    
    def _update_location_info(self, loc: Dict[str, Any]) -> None:
        """更新地点信息"""
        loc_name = loc["name"]
        if loc_name not in self.metadata["world_knowledge_base"]["locations"]:
            self.metadata["world_knowledge_base"]["locations"][loc_name] = {
                "description": loc["description"],
                "first_appearance": self.chapters[-1].number,
                "atmosphere": loc.get("atmosphere", "")
            }
    
    def _update_event_info(self, events: List[Dict[str, Any]]) -> None:
        """更新事件信息"""
        self.metadata["world_knowledge_base"]["events"].append({
            "chapter": self.chapters[-1].number,
            "events": events
        })
    
    def _update_item_info(self, item: Dict[str, Any]) -> None:
        """更新物品信息"""
        item_name = item["name"]
        if item_name not in self.metadata["world_knowledge_base"]["items"]:
            self.metadata["world_knowledge_base"]["items"][item_name] = {
                "significance": item["significance"],
                "first_appearance": self.chapters[-1].number,
                "effects": item.get("effects", [])
            }
    
    def _init_global_metadata(self) -> None:
        """初始化全局元数据"""
        self.metadata = {
            'title': self.file_path.stem,
            'total_chapters': len(self.chapters),
            'chapters': [],
            'world_knowledge_base': {
                'characters': {},
                'locations': {},
                'events': [],
                'items': {},
                'relationships': {},
                'story_arcs': [],
                'character_development': {},
                'relationship_network': {},
                'world_rules': {},
                'plot_triggers': []
            },
            'story_branches': [],
            'character_perspectives': {
                'protagonist': [],
                'supporting': [],
                'observer': []
            },
            'interaction_points': []
        }
    
    def _create_vector_store(self) -> Path:
        """创建向量存储"""
        documents = []
        for chapter in self.chapters:
            chunks = self.text_splitter.split_text(chapter.content)
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "chapter": chapter.number,
                        "chunk": i,
                        "title": chapter.title
                    }
                )
                documents.append(doc)
        
        vector_store = FAISS.from_documents(documents, self.embeddings)
        vector_store_path = settings.VECTOR_DIR / f"{self.file_path.stem}.faiss"
        vector_store.save_local(str(vector_store_path))
        
        return vector_store_path
    
    def _save_results(self) -> None:
        """保存所有处理结果"""
        # 创建基础目录
        novels_dir = settings.DATA_DIR / 'novels'
        summaries_dir = settings.DATA_DIR / 'summaries'
        vectors_dir = settings.DATA_DIR / 'vectors'
        chapters_dir = settings.DATA_DIR / 'chapters'  # 新增章节原文目录
        
        for dir_path in [novels_dir, summaries_dir, vectors_dir, chapters_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 保存原始章节内容
        novel_file = novels_dir / f"{self.file_path.stem}.txt"
        with open(novel_file, 'w', encoding='utf-8') as f:
            for chapter in self.chapters:
                f.write(f"{chapter.title}\n\n")
                f.write(f"{chapter.content}\n\n")
                f.write("=" * 80 + "\n\n")
        
        # 保存每个章节的原文内容（新增）
        novel_chapters_dir = chapters_dir / self.file_path.stem
        novel_chapters_dir.mkdir(parents=True, exist_ok=True)
        for chapter in self.chapters:
            chapter_file = novel_chapters_dir / f"chapter_{chapter.number:03d}.txt"
            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(f"{chapter.title}\n\n")
                f.write(chapter.content)
        
        # 保存摘要
        summary_file = summaries_dir / f"{self.file_path.stem}_summaries.json"
        summaries = {
            'title': self.file_path.stem,
            'chapters': [
                {
                    'number': chapter.number,
                    'title': chapter.title,
                    'summary': chapter.summary
                }
                for chapter in self.chapters
            ]
        }
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
        
        # 扩展元数据结构
        self.metadata.update({
            'story_branches': [],  # 用于存储可能的剧情分支
            'character_perspectives': {  # 不同视角的角色设定
                'protagonist': [],  # 主角视角
                'supporting': [],   # 配角视角
                'observer': []      # 观察者视角
            },
            'interaction_points': []  # 用户可交互的剧情节点
        })
        
        # 更新知识库结构
        self.metadata['world_knowledge_base'].update({
            'story_arcs': [],          # 主要剧情线
            'character_development': {},  # 角色发展轨迹
            'relationship_network': {},   # 人物关系网络
            'world_rules': {},           # 世界观设定
            'plot_triggers': []          # 剧情触发条件
        })
        
        # 保存元数据
        metadata_file = vectors_dir / f"{self.file_path.stem}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def _prepare_metadata_for_json(self) -> None:
        """准备元数据以进行JSON序列化"""
        # 转换字典为列表
        self.metadata['world_knowledge_base']['locations'] = list(
            self.metadata['world_knowledge_base']['locations'].values()
        )
        self.metadata['world_knowledge_base']['items'] = list(
            self.metadata['world_knowledge_base']['items'].values()
        )
        self.metadata['world_knowledge_base']['characters'] = list(
            self.metadata['world_knowledge_base']['characters'].values()
        ) 