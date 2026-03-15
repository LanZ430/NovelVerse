import streamlit as st  
import os  
import sys  
import logging  
from pathlib import Path  
import json  
  
# 添加上级目录到路径  
current_dir = Path(__file__).parent  
parent_dir = current_dir.parent  
sys.path.append(str(parent_dir.parent))  
  
# 修改导入路径，适应在agent/ui目录下运行  
try:  
    from agent.core.agent_coordinator import AgentCoordinator  
    from agent.core.document_agent import DocumentAgent  
    from agent.core.knowledge_agent import KnowledgeAgent  
    from agent.core.interaction import InteractionAgent  
except ModuleNotFoundError:  
    # 当在ui目录运行时，调整导入路径  
    from core.agent_coordinator import AgentCoordinator  
    from core.document_agent import DocumentAgent  
    from core.knowledge_agent import KnowledgeAgent  
    from core.interaction import InteractionAgent 
