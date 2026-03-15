@echo off
setlocal

REM 获取脚本所在目录的父目录（项目根目录）
set "PROJECT_ROOT=%~dp0.."

REM 创建 tools 目录（如果不存在）
if not exist "%PROJECT_ROOT%\tools" mkdir "%PROJECT_ROOT%\tools"

REM 检查 poppler 是否已经解压
if not exist "%PROJECT_ROOT%\tools\poppler" (
    echo 请先下载 poppler-utils 并解压到 %PROJECT_ROOT%\tools\poppler 目录
    echo 下载地址: https://github.com/oschwartz10612/poppler-windows/releases/
    echo 1. 下载最新的 Release-xx.xx.x.zip
    echo 2. 解压到 %PROJECT_ROOT%\tools\poppler 目录
    echo 3. 再次运行此脚本
    exit /b 1
)

REM 将 poppler bin 目录添加到 PATH
set "PATH=%PROJECT_ROOT%\tools\poppler\Library\bin;%PATH%"

REM 验证 pdftotext 是否可用
pdftotext -v >nul 2>&1
if errorlevel 1 (
    echo pdftotext 工具未正确安装
    echo 请确保已将 poppler 解压到正确的位置
) else (
    echo pdftotext 工具已成功配置！
    echo 现在可以运行 PDF 转换脚本了
)

REM 保持命令窗口打开，使环境变量生效
cmd /k 