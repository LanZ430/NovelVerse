import pdfplumber
import PyPDF2
from pathlib import Path
from typing import List, Dict, Optional
import re

class PDFProcessor:
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.chapters: List[Dict] = []
        self.metadata: Dict = {
            "title": "",
            "author": "",
            "dedication": "",
            "preface": ""
        }
        
    def extract_text(self) -> str:
        """从PDF中提取文本内容"""
        text = ""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            # 尝试使用备用方法
            try:
                with open(self.pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
            except Exception as e:
                print(f"Backup method also failed: {e}")
                return ""
        return text
    
    def clean_text(self, text: str) -> str:
        """清理和格式化提取的文本"""
        # 保留必要的换行，但删除连续的换行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 只处理明显的多余空格（连续两个以上的空格）
        text = re.sub(r'  +', ' ', text)
        
        # 修复特殊分隔符
        text = re.sub(r'[★\*]{3,}', '\n★ ★ ★\n', text)
        
        return text.strip()
    
    def extract_metadata(self, text: str) -> None:
        """提取元数据（标题、作者、献词等）"""
        lines = text.split('\n')
        
        # 查找标题和作者（在开头的几行中）
        for i, line in enumerate(lines[:5]):  # 只检查前5行
            # 检测标题
            title_match = re.search(r'《\s*(.+?)\s*》', line)
            if title_match and not self.metadata["title"]:
                self.metadata["title"] = re.sub(r'\s+', '', title_match.group(1))
            
            # 检测作者
            author_match = re.search(r'[（(](.+?)[)）].*?(?:著|原著|$)', line)
            if author_match and not self.metadata["author"]:
                self.metadata["author"] = re.sub(r'\s+', '', author_match.group(1))
            
            if self.metadata["title"] and self.metadata["author"]:
                break
        
        # 检测献词
        for line in lines:
            if line.startswith('献给') or '献词' in line:
                self.metadata["dedication"] = line + "\n"
                break
    
    def detect_chapters(self, text: str) -> List[Dict]:
        """检测和提取章节"""
        # 扩展章节标题的模式
        chapter_patterns = [
            # 罗马数字章节（更宽松的匹配）
            r'(?:^|\n)(?:\s*)((?:X{0,3})(?:IX|IV|V?I{0,3}))(?:\s*[.、]?\s*)([^\n]+)',
            # 阿拉伯数字章节
            r'第\d+章\s*[^\n]+',
            # 中文数字章节
            r'第[一二三四五六七八九十百千]+章\s*[^\n]+',
            # 英文章节
            r'Chapter\s+\d+[:\s]+[^\n]+',
            # 特殊分隔符章节
            r'★\s*★\s*★\s*[^\n]*'
        ]
        
        chapters = []
        current_content = []
        
        lines = text.split('\n')
        
        for line in lines:
            is_chapter_title = False
            
            # 检查是否是章节标题
            for pattern in chapter_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    # 如果有累积的内容，保存为一个章节
                    if current_content:
                        chapters.append({
                            "title": "",  # 无标题章节
                            "content": "\n".join(current_content)
                        })
                        current_content = []
                    
                    # 提取罗马数字章节的标题
                    if pattern == chapter_patterns[0]:  # 罗马数字模式
                        chapter_num = match.group(1)
                        chapter_title = match.group(2)
                        title = f"{chapter_num}. {chapter_title}"
                    else:
                        title = line.strip()
                    
                    chapters.append({
                        "title": title,
                        "content": ""
                    })
                    is_chapter_title = True
                    break
            
            # 如果不是章节标题，添加到当前内容
            if not is_chapter_title and line.strip():
                if not chapters:
                    current_content.append(line)
                else:
                    chapters[-1]["content"] += line + "\n"
        
        # 处理最后的内容
        if current_content:
            chapters.append({
                "title": "",
                "content": "\n".join(current_content)
            })
        
        return chapters
    
    def save_as_txt(self, output_path: Path) -> None:
        """将处理后的内容保存为txt文件"""
        # 提取文本
        text = self.extract_text()
        # 清理文本
        text = self.clean_text(text)
        # 提取元数据
        self.extract_metadata(text)
        # 检测章节
        self.chapters = self.detect_chapters(text)
        
        # 保存为txt文件
        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入标题和作者
            if self.metadata["title"]:
                f.write(f'《{self.metadata["title"]}》\n')
            if self.metadata["author"]:
                f.write(f'{self.metadata["author"]}\n\n')
            
            # 写入献词
            if self.metadata["dedication"]:
                f.write(f'{self.metadata["dedication"]}\n\n')
            
            # 写入前言
            if self.metadata["preface"]:
                f.write(f'{self.metadata["preface"]}\n\n')
                f.write('★ ★ ★\n\n')
            
            # 写入章节内容
            for chapter in self.chapters:
                f.write(f'{chapter["title"]}\n\n')
                f.write(f'{chapter["content"]}\n\n') 