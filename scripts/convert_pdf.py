import sys
import os
from pathlib import Path
import subprocess
import shutil

def setup_paths():
    """设置必要的目录结构"""
    data_dir = Path(__file__).parent.parent / "data"
    novel_dir = data_dir / "novels"
    novel_dir.mkdir(parents=True, exist_ok=True)
    return novel_dir

def check_pdftotext():
    """检查是否安装了pdftotext"""
    return shutil.which('pdftotext') is not None

def convert_pdf_to_txt(input_pdf: Path, output_txt: Path):
    """使用pdftotext转换PDF到TXT"""
    try:
        # -layout：保持原始布局
        # -nopgbrk：移除分页符
        # -enc UTF-8：使用UTF-8编码
        subprocess.run([
            'pdftotext',
            '-layout',
            '-nopgbrk',
            '-enc', 'UTF-8',
            str(input_pdf),
            str(output_txt)
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"转换失败: {e}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 pdftotext 工具。请先安装 poppler-utils。")
        print("Windows: 从 https://github.com/oschwartz10612/poppler-windows/releases/ 下载")
        print("Linux: sudo apt-get install poppler-utils")
        print("macOS: brew install poppler")
        return False

def main():
    if len(sys.argv) < 2:
        print("使用方法: python convert_pdf.py <PDF文件路径>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    
    # 检查输入文件
    if not input_path.exists():
        print(f"错误: 文件不存在: {input_path}")
        sys.exit(1)
    
    if input_path.suffix.lower() != '.pdf':
        print(f"错误: 不是PDF文件: {input_path}")
        sys.exit(1)
    
    # 检查pdftotext是否可用
    if not check_pdftotext():
        print("请先安装 pdftotext 工具")
        sys.exit(1)
    
    # 设置输出路径
    novel_dir = setup_paths()
    output_path = novel_dir / f"{input_path.stem}.txt"
    
    # 如果输出文件已存在，添加数字后缀
    if output_path.exists():
        i = 1
        while True:
            new_path = novel_dir / f"{input_path.stem}_{i}.txt"
            if not new_path.exists():
                output_path = new_path
                break
            i += 1
    
    # 转换PDF到TXT
    print(f"正在转换 {input_path.name} ...")
    if convert_pdf_to_txt(input_path, output_path):
        print(f"转换成功！输出文件保存在: {output_path}")
    else:
        print("转换失败")
        sys.exit(1)

if __name__ == "__main__":
    main() 