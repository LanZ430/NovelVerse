import pytest
from pathlib import Path
from app.core.document import NovelProcessor, Chapter, TextChunker
from config.config import settings

@pytest.fixture
def sample_novel_content():
    return """第一章 序幕
这是第一章的内容。
故事从这里开始。

第二章 转折
这是第二章的内容。
故事继续发展。
"""

@pytest.fixture
def temp_novel_file(tmp_path, sample_novel_content):
    novel_file = tmp_path / "test_novel.txt"
    novel_file.write_text(sample_novel_content, encoding='utf-8')
    return novel_file

def test_novel_processor_initialization(temp_novel_file):
    processor = NovelProcessor(temp_novel_file)
    assert processor.novel_path == temp_novel_file
    assert isinstance(processor.chapters, list)
    assert len(processor.chapters) == 0

def test_chapter_splitting(temp_novel_file):
    processor = NovelProcessor(temp_novel_file)
    processor.load_novel()
    
    assert len(processor.chapters) == 2
    assert processor.chapters[0].title == "第一章 序幕"
    assert "这是第一章的内容" in processor.chapters[0].content
    assert processor.chapters[1].title == "第二章 转折"
    assert "这是第二章的内容" in processor.chapters[1].content

def test_text_chunker():
    chunker = TextChunker(chunk_size=10, chunk_overlap=2)
    text = "这是一个测试文本，用于测试分块功能是否正常工作。"
    chunks = chunker.split_text(text)
    
    assert len(chunks) > 0
    # 验证块大小
    for chunk in chunks[:-1]:  # 除最后一块外
        assert len(chunk) <= 10
    # 验证重叠
    if len(chunks) > 1:
        assert chunks[0][-2:] == chunks[1][:2]

def test_save_processed_data(temp_novel_file, tmp_path):
    # 配置临时输出目录
    settings.SUMMARY_DIR = tmp_path / "summaries"
    settings.SUMMARY_DIR.mkdir(exist_ok=True)
    
    processor = NovelProcessor(temp_novel_file)
    processor.load_novel()
    processor.generate_summaries()  # 这会生成空的摘要
    processor.save_processed_data()
    
    # 验证文件是否被创建
    output_dir = settings.SUMMARY_DIR / temp_novel_file.stem
    assert output_dir.exists()
    assert (output_dir / "summaries.json").exists()
    assert (output_dir / "metadata.json").exists()

@pytest.mark.asyncio
async def test_generate_summaries(temp_novel_file):
    processor = NovelProcessor(temp_novel_file)
    processor.load_novel()
    await processor.generate_summaries()
    
    # 验证是否每个章节都有摘要
    for chapter in processor.chapters:
        assert chapter.summary != ""
        assert len(chapter.summary) > 0

def test_extract_metadata(temp_novel_file):
    processor = NovelProcessor(temp_novel_file)
    processor.load_novel()
    processor.extract_metadata()
    
    # 验证元数据是否被提取
    assert processor.metadata
    assert "characters" in processor.metadata
    assert "locations" in processor.metadata
    assert "events" in processor.metadata 