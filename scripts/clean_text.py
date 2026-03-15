import sys
from pathlib import Path
import re

def clean_text(text: str) -> str:
    """清理文本内容"""
    # 分割成行
    lines = text.split('\n')
    
    # 清理每一行
    cleaned_lines = []
    current_paragraph = []
    
    for line in lines:
        # 去除行首尾空白
        line = line.strip()
        
        # 跳过空行
        if not line:
            if current_paragraph:
                # 合并当前段落并添加到结果中
                cleaned_lines.append(' '.join(current_paragraph))
                current_paragraph = []
            continue
        
        # 检查是否是章节标题（罗马数字或特殊标记）
        if re.match(r'^[IVX]+$', line) or line.startswith('★'):
            if current_paragraph:
                cleaned_lines.append(' '.join(current_paragraph))
                current_paragraph = []
            cleaned_lines.extend(['', line, ''])
            continue
            
        # 检查是否是标题（书名、作者、献词等）
        if re.match(r'^《.*》$', line) or '献给' in line:
            if current_paragraph:
                cleaned_lines.append(' '.join(current_paragraph))
                current_paragraph = []
            cleaned_lines.extend(['', line, ''])
            continue
        
        # 如果行以标点符号开头，说明是上一行的延续
        if line and line[0] in '，。；：！？、':
            if current_paragraph:
                current_paragraph[-1] = current_paragraph[-1] + line
            continue
            
        # 如果当前行很短（少于10个字符）并且不以标点结尾，可能是标题
        if len(line) < 10 and not line[-1] in '。！？"':
            if current_paragraph:
                cleaned_lines.append(' '.join(current_paragraph))
                current_paragraph = []
            cleaned_lines.extend(['', line, ''])
            continue
            
        # 普通段落文本
        current_paragraph.append(line)
    
    # 处理最后一个段落
    if current_paragraph:
        cleaned_lines.append(' '.join(current_paragraph))
    
    # 合并行，确保段落之间只有一个空行
    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def process_file(input_path: Path) -> None:
    """处理单个文件"""
    # 读取文件
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # 清理文本
    cleaned_text = clean_text(text)
    
    # 保存清理后的文本
    output_path = input_path.parent / f"{input_path.stem}_cleaned{input_path.suffix}"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_text)
    
    print(f"清理完成！输出文件保存在: {output_path}")

def main():
    if len(sys.argv) < 2:
        print("使用方法: python clean_text.py <文本文件路径>")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    
    if not input_path.exists():
        print(f"错误: 文件不存在: {input_path}")
        sys.exit(1)
    
    process_file(input_path)

if __name__ == "__main__":
    main() 