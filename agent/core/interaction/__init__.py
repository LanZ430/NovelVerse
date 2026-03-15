"""互动代理模块包，负责处理用户与故事的交互

该包提供了一套完整的交互处理系统，包括场景生成、用户输入评估、记忆管理和图像生成等功能。
"""

# 导入子模块
from .interaction_agent import InteractionAgent as CoreInteractionAgent
from .scene_generator import SceneGenerator
from .input_evaluator import InputEvaluator
from .memory_manager import MemoryManager
from .image_generator import ImageGenerator
from .state_manager import StateManager
from .adapter import InteractionAgentAdapter

# 为了与现有代码兼容，这里暴露适配器类为InteractionAgent
InteractionAgent = InteractionAgentAdapter

# 导出主要类
__all__ = [
    'InteractionAgent',
    'CoreInteractionAgent',
    'SceneGenerator',
    'InputEvaluator',
    'MemoryManager',
    'ImageGenerator',
    'StateManager',
    'InteractionAgentAdapter'
] 