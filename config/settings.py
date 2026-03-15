from pathlib import Path
from typing import Dict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    NOVEL_DIR: Path = DATA_DIR / "novels"
    SUMMARY_DIR: Path = DATA_DIR / "summaries"
    VECTOR_DIR: Path = DATA_DIR / "vectors"
    TEMP_DIR: Path = NOVEL_DIR / "temp_sample_xiaowangzi"

    # API Configuration
    VOLCENGINE_API_KEY: str = ""
    VOLCENGINE_API_SECRET: str = ""
    
    # LLM Settings
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.9
    
    # Vector Database Settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    # Story Generation Settings
    MAX_HISTORY_TURNS: int = 10
    MAX_CONTEXT_LENGTH: int = 4096
    
    # Image Generation Settings
    IMAGE_SIZE: str = "1024x1024"
    IMAGE_QUALITY: str = "standard"
    
    # Video Generation Settings
    VIDEO_LENGTH: int = 10  # seconds
    VIDEO_FPS: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()

# Create necessary directories
for dir_path in [settings.NOVEL_DIR, settings.SUMMARY_DIR, settings.VECTOR_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)