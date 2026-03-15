"""
配置文件：包含应用所需的配置参数
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict
from pydantic_settings import BaseSettings

# 加载环境变量
load_dotenv()

# 基础路径配置
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
NOVEL_DIR = DATA_DIR / "novels"
VECTOR_DIR = DATA_DIR / "vectors"

# 确保目录存在
for dir_path in [DATA_DIR, NOVEL_DIR, VECTOR_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 文本处理配置
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

class Settings(BaseSettings):
    # 项目基础配置
    PROJECT_ROOT: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    NOVEL_DIR: Path = NOVEL_DIR
    SUMMARY_DIR: Path = DATA_DIR / "summaries"
    VECTOR_DIR: Path = VECTOR_DIR
    
    # 火山引擎API配置
    VOLCENGINE_API_KEY: str = ""
    VOLCENGINE_API_SECRET: str = ""
    VOLCENGINE_REGION: str = "cn-beijing"
    
    # LLM模型配置
    MODEL_NAME: str = "chatglm-v2"
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.7
    
    # 向量存储配置
    VECTOR_DIMENSION: int = 1536
    
    # 多模态生成配置
    IMAGE_SIZE: tuple = (512, 512)
    VIDEO_LENGTH: int = 10  # seconds
    
    # API配置
    DEEPSEEK_API_KEY: str = DEEPSEEK_API_KEY
    
    # 文本处理配置
    CHUNK_SIZE: int = CHUNK_SIZE
    CHUNK_OVERLAP: int = CHUNK_OVERLAP
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

# 确保必要的目录存在
for dir_path in [settings.DATA_DIR, settings.NOVEL_DIR, 
                 settings.SUMMARY_DIR, settings.VECTOR_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True) 