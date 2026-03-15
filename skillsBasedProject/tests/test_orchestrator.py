"""SkillOrchestrator 测试"""

import pytest
from pathlib import Path

# 添加项目根目录
import sys
_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))


def test_orchestrator_loads_skills():
    from agent.skills import SkillOrchestrator

    data_dir = _root.parent / "data" if (_root.parent / "data").exists() else _root / "data"
    orch = SkillOrchestrator(document_id="zh-xiaowangzi_1", data_dir=str(data_dir))

    assert "novel-metadata" in orch.skills
    assert "storyline-control" in orch.skills
    assert "image-generation" in orch.skills
    assert "memory-architecture" in orch.skills
    assert "voice-generation" in orch.skills


def test_get_context_for_scene():
    from agent.skills import SkillOrchestrator

    data_dir = _root.parent / "data" if (_root.parent / "data").exists() else _root / "data"
    orch = SkillOrchestrator(document_id="zh-xiaowangzi_1", data_dir=str(data_dir))

    ctx = orch.get_context_for_scene("小王子", 1)
    assert "character_info" in ctx
    assert "cross_chapter_memory" in ctx
    assert isinstance(ctx["cross_chapter_memory"], list)


def test_evaluate_input():
    from agent.skills import SkillOrchestrator

    orch = SkillOrchestrator(document_id="test", data_dir=str(_root / "data"))
    result = orch.evaluate_input("测试输入", {})
    assert "allow_continue" in result
    assert "level" in result


def test_generate_image_prompt():
    from agent.skills import SkillOrchestrator

    orch = SkillOrchestrator(document_id="test", data_dir=str(_root / "data"))
    scene = {"narrative": "场景描述", "key_elements": ["元素1"], "emotion_state": {"角色": "平静"}}
    prompt = orch.generate_image_prompt(scene)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
