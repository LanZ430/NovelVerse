"""ImageGeneration Skill：场景到图像提示词优化"""

from .prompt_builder import ImageGenerationSkill

def create_skill(document_id: str, data_dir: str, config: dict):
    return ImageGenerationSkill(document_id=document_id, data_dir=data_dir, config=config)
