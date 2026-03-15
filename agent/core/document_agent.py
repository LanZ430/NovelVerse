from typing import Dict, Any, List, Optional
import logging
import os
from pathlib import Path
import json
import re
from .base_agent import BaseAgent
from openai import OpenAI

logger = logging.getLogger(__name__)

class DocumentAgent(BaseAgent):
    """文档处理代理，负责文档上传、解析和预处理"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化文档处理代理
        
        Args:
            config: 配置信息，包括：
                - data_dir: 数据存储目录
                - supported_languages: 支持的语言列表
                - supported_formats: 支持的文件格式
        """
        super().__init__(config)
        self.data_dir = Path(self.config.get('data_dir', './data'))
        self.novel_dir = self.data_dir / 'novels'
        self.chapters_dir = self.data_dir / 'chapters'
        self.metadata_dir = self.data_dir / 'metadata'
        self.supported_languages = self.config.get('supported_languages', ['zh', 'en'])
        self.supported_formats = self.config.get('supported_formats', ['.txt', '.pdf', '.docx'])
        
    def initialize(self) -> bool:
        """初始化文档处理资源
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 创建必要的目录
            self.novel_dir.mkdir(parents=True, exist_ok=True)
            self.chapters_dir.mkdir(parents=True, exist_ok=True)
            self.metadata_dir.mkdir(parents=True, exist_ok=True)
            
            self.is_initialized = True
            logger.info(f"文档处理代理初始化成功，数据目录: {self.data_dir}")
            return True
        except Exception as e:
            logger.exception(f"文档处理代理初始化失败: {str(e)}")
            return False
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行文档处理
        
        Args:
            context: 上下文信息，包括：
                - file_path: 文件路径
                - language: 文档语言
                - content_percentage: 处理的文档百分比
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        super().execute(context)
        
        file_path = context.get('file_path')
        if not file_path:
            return {
                "status": "error",
                "message": "文件路径不能为空"
            }
            
        language = context.get('language', 'zh')
        if language not in self.supported_languages:
            return {
                "status": "error",
                "message": f"不支持的语言: {language}，支持的语言: {self.supported_languages}"
            }
            
        content_percentage = context.get('content_percentage', 100)
        if not (0 < content_percentage <= 100):
            return {
                "status": "error",
                "message": f"无效的内容百分比: {content_percentage}，应该在1-100之间"
            }
        
        # 处理文档
        try:
            result = self._process_document(file_path, language, content_percentage)
            return {
                "status": "success",
                "document_info": result,
                "message": "文档处理成功"
            }
        except Exception as e:
            logger.exception(f"文档处理失败: {str(e)}")
            return {
                "status": "error",
                "message": f"文档处理出错: {str(e)}"
            }
    
    def _process_document(self, file_path: str, language: str, content_percentage: int) -> Dict[str, Any]:
        """处理文档
        
        Args:
            file_path: 文件路径
            language: 文档语言
            content_percentage: 处理的文档百分比
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        logger.info(f"开始处理文档: {file_path}, 语言: {language}, 内容百分比: {content_percentage}%")
        
        # 验证文件是否存在
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
            
        # 验证文件格式
        if file_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}，支持的格式: {self.supported_formats}")
            
        # 读取文件内容
        content = self._read_file(file_path)
        
        # 基于百分比截取内容
        if content_percentage < 100:
            content_length = len(content)
            content = content[:int(content_length * content_percentage / 100)]
            
        # 分章节处理
        chapters = self._split_into_chapters(content, language)
        
        # 生成唯一的文档ID
        document_id = f"{language}-{file_path.stem}_{len(chapters)}"
        
        # 保存章节
        novel_dir = self.novel_dir / document_id
        novel_dir.mkdir(parents=True, exist_ok=True)
        
        chapters_dir = self.chapters_dir / document_id
        chapters_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_dir = self.metadata_dir / document_id
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存原始文件
        with open(novel_dir / file_path.name, "wb") as f:
            with open(file_path, "rb") as source:
                f.write(source.read())
                
        # 保存章节文件
        for i, chapter in enumerate(chapters):
            chapter_file = chapters_dir / f"chapter_{i+1:03d}.txt"
            with open(chapter_file, "w", encoding="utf-8") as f:
                f.write(chapter)
                
        # 生成元数据
        metadata = {
            "document_id": document_id,
            "title": file_path.stem,
            "language": language,
            "original_file": file_path.name,
            "content_percentage": content_percentage,
            "total_chapters": len(chapters),
            "processing_date": self._get_current_timestamp()
        }
        
        with open(metadata_dir / "document_info.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
        # 生成小说元数据摘要
        logger.info("Generating novel metadata summary...")
        self.generate_novel_metadata_summary(document_id, language)
            
        logger.info(f"文档处理完成: {document_id}, 共{len(chapters)}章")
        
        return metadata
    
    def _read_file(self, file_path: Path) -> str:
        """读取文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件内容
        """
        if file_path.suffix.lower() == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif file_path.suffix.lower() == ".pdf":
            # 这里需要集成PDF读取功能，可以使用PyPDF2或pdfplumber等库
            raise NotImplementedError("PDF文件格式暂未实现")
        elif file_path.suffix.lower() == ".docx":
            # 这里需要集成DOCX读取功能，可以使用python-docx库
            raise NotImplementedError("DOCX文件格式暂未实现")
        else:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")
    
    def _split_into_chapters(self, content: str, language: str) -> List[str]:
        """将内容分割为章节
        
        Args:
            content: 文件内容
            language: 文档语言
            
        Returns:
            List[str]: 章节列表
        """
        logger.info("Starting chapter splitting...")
        
        # 1. 检测章节模式
        chapter_pattern = self._detect_chapter_pattern(content, language)
        logger.info(f"Using chapter pattern: {chapter_pattern}")
        
        # 2. 分割内容
        chapter_splits = re.split(f'({chapter_pattern})', content)
        logger.info(f"Found {len(chapter_splits)} potential chapter splits")
        
        # 3. 处理分割结果
        current_chapter = None
        current_content = []
        chapter_number = 0
        chapters = []
        
        for i, split in enumerate(chapter_splits):
            if not split.strip():
                continue
            
            if re.search(chapter_pattern, split):
                # 如果找到章节标题，且已有当前章节，则保存当前章节
                if current_chapter:
                    chapter_text = current_chapter + "\n\n" + "\n".join(current_content)
                    chapters.append(chapter_text.strip())
                    logger.info(f"Added chapter {chapter_number}: {current_chapter}")
                
                # 更新为新章节
                current_chapter = split.strip()
                current_content = []
                chapter_number += 1
            else:
                current_content.append(split.strip())
        
        # 处理最后一章
        if current_chapter:
            chapter_text = current_chapter + "\n\n" + "\n".join(current_content)
            chapters.append(chapter_text.strip())
            logger.info(f"Added final chapter {chapter_number}: {current_chapter}")
        
        if not chapters:
            logger.warning("No chapters were found after splitting, treating entire content as one chapter")
            chapters = [content]
            
        logger.info(f"Successfully split content into {len(chapters)} chapters")
        return chapters
    
    def _detect_chapter_pattern(self, content: str, language: str) -> str:
        """检测章节标记模式
        
        Args:
            content: 文件内容
            language: 文档语言
            
        Returns:
            str: 章节标记模式
        """
        # 基于语言定义可能的章节模式
        if language == "zh":
            patterns = {
                'chinese_num': r'第[一二三四五六七八九十百千]+章',
                'chinese_digit': r'第\d+章',
                'chinese_num_section': r'第[一二三四五六七八九十百千]+节',
                'chinese_digit_section': r'第\d+节',
                'chinese_num_part': r'第[一二三四五六七八九十百千]+回',
                'chinese_digit_part': r'第\d+回',
                'mixed': r'第.+章.*\n',
                'chinese_dot': r'[一二三四五六七八九十]+[\.\、]',
                'number_dot': r'\d+[\.\、]',
            }
        else:  # 默认英文
            patterns = {
                'english_lower': r'chapter\s+\d+',
                'english_upper': r'CHAPTER\s+\d+',
                'english_part_lower': r'part\s+\d+',
                'english_part_upper': r'PART\s+\d+',
                'roman_centered': r'\n\s*[IVXLC]+\s*\n',
                'roman_regular': r'\n[IVXLC]+\n',
                'simple_roman': r'[IVXLC]+[\.\、]',
                'number_dot': r'\d+[\.\、]',
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
        if pattern_counts:
            best_pattern = max(pattern_counts.items(), key=lambda x: x[1])[0]
            logger.info(f"Selected best pattern: {best_pattern} with {pattern_counts[best_pattern]} matches")
            
            if pattern_counts[best_pattern] == 0:
                logger.warning("No chapter patterns found in content")
                # 没有找到任何模式，返回通用的模式或基于语言的默认模式
                if language == "zh":
                    return r'第\s*[一二三四五六七八九十百千万零\d]+\s*章'
                else:
                    return r'chapter\s*\d+'
                
            return patterns[best_pattern]
        else:
            logger.warning("No patterns defined for this language")
            return r'chapter\s*\d+'
    
    def generate_novel_metadata_summary(self, document_id: str, language: str) -> str:
        """生成小说元数据摘要，包括时间线、世界观、风格、主题等
        
        Args:
            document_id: 文档ID
            language: 文档语言
            
        Returns:
            str: 元数据摘要（500-1000字）
        """
        try:
            # 获取章节内容
            chapters_dir = self.chapters_dir / document_id
            if not chapters_dir.exists():
                logger.warning(f"章节目录不存在: {chapters_dir}")
                return ""
                
            # 收集章节标题和内容样本
            sample_content = ""
            chapter_titles = []
            
            # 收集样本章节内容和标题
            chapter_files = sorted(list(chapters_dir.glob("chapter_*.txt")))
            sample_chapters = min(5, len(chapter_files))
            
            for i in range(sample_chapters):
                chapter_idx = i * len(chapter_files) // sample_chapters
                if chapter_idx < len(chapter_files):
                    chapter_file = chapter_files[chapter_idx]
                    chapter_num = int(chapter_file.stem.split('_')[1])
                    
                    # 获取章节内容的一部分（前2000字符）
                    with open(chapter_file, 'r', encoding='utf-8') as f:
                        chapter_content = f.read()
                        chapter_title = chapter_content.splitlines()[0] if chapter_content.splitlines() else f"第{chapter_num}章"
                        chapter_titles.append(f"第{chapter_num}章: {chapter_title if chapter_title else '无标题'}")
                        
                        sample_content += f"\n## 第{chapter_num}章\n"
                        sample_content += chapter_content[:2000] + "...\n"
            
            # 确定语言
            is_english = document_id.startswith("en-") if document_id else (language == "en")
            
            # 构建提示词
            if is_english:
                prompt = f"""As a literary analyst, create a comprehensive metadata summary for this novel. The summary will be used to enhance the immersive reading experience by providing context to an AI system.

## Basic Information
- Title: {document_id}
- Total Chapters: {len(chapter_files)}
- Chapter Titles: {", ".join(chapter_titles[:5])}...

## Sample Content
{sample_content}

Create a rich, informative summary (500-1000 words) that includes:

1. TIMELINE: Key events and chronology of the story
2. WORLD-BUILDING: Setting, time period, and distinctive features of the story's world
3. WRITING STYLE: Literary techniques, narrative voice, and stylistic elements
4. CHARACTER DEVELOPMENT: Main characters' psychological depth and growth patterns
5. THEMES: Core ideas and philosophical elements explored in the text
6. MOTIFS: Recurring images, concepts, or symbols

Format your response as a JSON object with the following structure:
{{
  "timeline": "Brief timeline of major events",
  "world_building": "Description of the novel's setting and world",
  "style": "Analysis of writing style and narrative techniques",
  "character_development": "Overview of character arcs and psychological elements",
  "themes": "Main themes and philosophical ideas",
  "motifs": "Recurring symbols and motifs"
}}

This metadata will help AI generate more consistent and contextually appropriate responses during interactive storytelling.
"""
            else:
                prompt = f"""作为文学分析专家，请为这部小说创建一个全面的元数据摘要。这个摘要将用于增强沉浸式阅读体验，为AI系统提供上下文信息。

## 基本信息
- 标题: {document_id}
- 总章节数: {len(chapter_files)}
- 章节标题: {", ".join(chapter_titles[:5])}...

## 样本内容
{sample_content}

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

这些元数据将帮助AI在交互式讲故事过程中生成更一致和更符合上下文的回应。
"""

            # 调用LLM生成摘要
            try:
                client = OpenAI(
                    api_key=self.config.get('llm_api_key'),
                    base_url="https://api.deepseek.com"
                )
                
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000
                )
                
                summary = response.choices[0].message.content
                
                # 保存摘要到文件
                metadata_dir = self.metadata_dir / document_id
                metadata_dir.mkdir(parents=True, exist_ok=True)
                
                world_metadata_file = metadata_dir / 'world_metadata.json'
                
                try:
                    # 检查是否是有效的JSON，如果是则解析后再保存
                    summary_json = json.loads(summary)
                    
                    with open(world_metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(summary_json, f, ensure_ascii=False, indent=2)
                        
                    logger.info(f"Novel metadata summary saved to {world_metadata_file}")
                    return summary
                    
                except json.JSONDecodeError:
                    # 如果不是有效的JSON，只保存文本内容
                    with open(world_metadata_file, 'w', encoding='utf-8') as f:
                        f.write(summary)
                    
                    logger.warning(f"Generated summary is not valid JSON, saved as text to {world_metadata_file}")
                    return summary
            except Exception as e:
                logger.error(f"Error calling LLM API: {str(e)}")
                return ""
                
        except Exception as e:
            logger.error(f"Error generating novel metadata summary: {str(e)}")
            return ""
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳
        
        Returns:
            str: 时间戳字符串
        """
        import datetime
        return datetime.datetime.now().isoformat()
    
    def list_available_documents(self) -> List[Dict[str, Any]]:
        """列出所有可用的文档
        
        Returns:
            List[Dict[str, Any]]: 文档列表
        """
        documents = []
        
        if not self.metadata_dir.exists():
            return documents
            
        for doc_dir in self.metadata_dir.iterdir():
            if doc_dir.is_dir():
                info_file = doc_dir / "document_info.json"
                if info_file.exists():
                    try:
                        with open(info_file, "r", encoding="utf-8") as f:
                            doc_info = json.load(f)
                            documents.append(doc_info)
                    except Exception as e:
                        logger.error(f"读取文档信息失败: {info_file}, 错误: {str(e)}")
        
        return documents
    
    def get_document_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取文档信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Optional[Dict[str, Any]]: 文档信息
        """
        info_file = self.metadata_dir / document_id / "document_info.json"
        
        if not info_file.exists():
            return None
            
        try:
            with open(info_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取文档信息失败: {info_file}, 错误: {str(e)}")
            return None 