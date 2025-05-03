"""
用于测试小说处理器功能的脚本
"""

import logging
import PyPDF2
from pathlib import Path
from typing import Tuple
import sys

# Add the project root directory to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from app.core.document import NovelProcessor
from config.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_partial_pdf(pdf_path: str, sample_ratio: float = 0.2) -> Tuple[str, Path]:
    """提取PDF文件的部分内容用于测试
    
    Args:
        pdf_path: PDF文件路径
        sample_ratio: 采样比例，默认0.2（即20%）
        
    Returns:
        Tuple[str, Path]: 提取的内容和临时文件路径
    """
    logger.info(f"开始提取PDF文件部分内容，采样比例: {sample_ratio}")
    
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        sample_pages = int(total_pages * sample_ratio)
        
        # 确保至少处理1页
        sample_pages = max(1, sample_pages)
        logger.info(f"总页数: {total_pages}, 将处理: {sample_pages} 页")
        
        # 提取内容
        content = []
        for i in range(sample_pages):
            page = pdf_reader.pages[i]
            content.append(page.extract_text())
    
    # 创建临时文件
    temp_path = Path(pdf_path).parent / f"temp_sample_{Path(pdf_path).stem}.txt"
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(content))
    
    logger.info(f"已创建采样文件: {temp_path}")
    return '\n'.join(content), temp_path

def test_novel_processing(file_path: str, sample_ratio: float = 0.2) -> None:
    """测试小说处理功能
    
    Args:
        file_path: PDF文件路径
        sample_ratio: 采样比例，默认0.2（即20%）
    """
    try:
        logger.info(f"开始处理文件: {file_path}")
        
        # 提取部分内容
        _, temp_path = extract_partial_pdf(file_path, sample_ratio)
        
        try:
            # 初始化处理器
            processor = NovelProcessor(temp_path)
            
            # 处理小说
            logger.info("开始文档处理流程...")
            processor.process_novel()
            
            # 输出处理结果统计
            logger.info(f"总章节数: {len(processor.chapters)}")
            
            # 检查第一章的处理结果
            if processor.chapters:
                first_chapter = processor.chapters[0]
                logger.info(f"\n第一章信息:")
                logger.info(f"标题: {first_chapter.title}")
                logger.info(f"内容长度: {len(first_chapter.content)} 字符")
                logger.info(f"摘要: {first_chapter.summary[:100]}...")
                
                # 检查章节原文是否已保存
                chapter_file = settings.DATA_DIR / 'chapters' / temp_path.stem / 'chapter_001.txt'
                if chapter_file.exists():
                    logger.info("章节原文已成功保存")
                    with open(chapter_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logger.info(f"原文内容长度: {len(content)} 字符")
                else:
                    logger.warning("未找到章节原文文件")
            
            logger.info("文档处理完成!")
            
        finally:
            # 清理临时文件
            if temp_path.exists():
                temp_path.unlink()
                logger.info("已清理临时文件")
        
    except Exception as e:
        logger.error(f"处理过程中出错: {str(e)}")
        raise

if __name__ == "__main__":
    # 这里填入您的PDF文件路径
    pdf_path = "D:/ACode/AIFoundationAgent/data/novels/xiaowangzi.pdf"
    test_novel_processing(pdf_path, sample_ratio=0.2)  # 处理20%的内容 