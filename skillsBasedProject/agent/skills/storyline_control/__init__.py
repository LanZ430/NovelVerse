"""StorylineControl Skill：故事线偏离度控制"""

from .divergence_manager import StorylineControlSkill

def create_skill(document_id: str, data_dir: str, config: dict):
    return StorylineControlSkill(document_id=document_id, data_dir=data_dir, config=config)
