"""MemoryArchitecture Skill：分层记忆管理"""

from .enhanced_memory_manager import MemoryArchitectureSkill

def create_skill(document_id: str, data_dir: str, config: dict):
    return MemoryArchitectureSkill(document_id=document_id, data_dir=data_dir, config=config)
