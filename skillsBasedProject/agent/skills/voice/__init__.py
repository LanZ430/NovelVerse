"""VoiceGeneration Skill：对话转语音"""

from .voice_service import VoiceGenerationSkill

def create_skill(document_id: str, data_dir: str, config: dict):
    return VoiceGenerationSkill(document_id=document_id, data_dir=data_dir, config=config)
