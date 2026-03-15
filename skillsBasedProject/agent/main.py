"""Skill 架构项目入口"""

import sys
import logging
from pathlib import Path

# 确保项目根目录在路径中
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_demo():
    """运行 Skill 编排器演示"""
    from agent.skills import SkillOrchestrator

    # 使用父项目的数据目录（若存在）
    data_dir = _root.parent / "data" if (_root.parent / "data").exists() else _root / "data"
    document_id = "zh-xiaowangzi_1"

    orchestrator = SkillOrchestrator(
        document_id=document_id,
        data_dir=str(data_dir),
        config={},
    )

    ctx = orchestrator.get_context_for_scene("小王子", 1)
    print("Context keys:", list(ctx.keys()))
    print("Character info:", ctx.get("character_info"))
    print("Cross chapter memory count:", len(ctx.get("cross_chapter_memory", [])))

    eval_result = orchestrator.evaluate_input("我想去探索新的星球", ctx)
    print("Evaluate result:", eval_result)

    scene = {"narrative": "小王子说：请给我画一只羊。", "key_elements": ["小王子", "羊"], "emotion_state": {"小王子": "期待"}}
    prompt = orchestrator.generate_image_prompt(scene)
    print("Image prompt:", prompt[:100] + "...")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Skill 架构沉浸式小说系统")
    parser.add_argument("command", choices=["demo", "ui"], nargs="?", default="demo", help="demo | ui")
    args = parser.parse_args()

    if args.command == "demo":
        run_demo()
    elif args.command == "ui":
        try:
            import streamlit.web.cli as stcli
            app_path = _root / "agent" / "ui" / "app.py"
            if app_path.exists():
                sys.argv = ["streamlit", "run", str(app_path)]
                stcli.main()
            else:
                print("UI 尚未实现，请运行: python -m agent.main demo")
        except ImportError:
            print("请安装 streamlit: pip install streamlit")


if __name__ == "__main__":
    main()
