"""NovelMetadata Skill：元数据管理"""

from .metadata_manager import NovelMetadataSkill

def create_skill(document_id: str, data_dir: str, config: dict):
    return NovelMetadataSkill(document_id=document_id, data_dir=data_dir, config=config)
