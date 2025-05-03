from typing import Dict, Any, List, Optional
import logging
import os
from pathlib import Path
import json
import re
from .base_agent import BaseAgent

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
        document_id = f"{file_path.stem}_{len(chapters)}"
        
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