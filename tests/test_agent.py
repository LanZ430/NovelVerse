import pytest
from pathlib import Path
from app.core.agent import StoryAgent
from app.core.knowledge import KnowledgeBase
from config.config import settings

@pytest.fixture
def sample_novel_id():
    return "test_novel"

@pytest.fixture
def mock_knowledge_base(sample_novel_id):
    kb = KnowledgeBase(sample_novel_id)
    # 添加一些测试数据
    kb.items = [
        {
            "content": "主角张三是一个勇敢的冒险家",
            "metadata": {"type": "character", "name": "张三"}
        },
        {
            "content": "故事发生在一个神秘的森林中",
            "metadata": {"type": "location", "name": "神秘森林"}
        }
    ]
    return kb

@pytest.fixture
def story_agent(sample_novel_id):
    return StoryAgent(novel_id=sample_novel_id)

def test_agent_initialization(story_agent, sample_novel_id):
    assert story_agent.novel_id == sample_novel_id
    assert story_agent.role == "observer"
    assert story_agent.memory is not None
    assert len(story_agent.tools) > 0

def test_role_prompt_generation(story_agent):
    # 测试不同角色的提示词生成
    story_agent.update_role("protagonist")
    prompt = story_agent._get_role_prompt()
    assert "第一人称" in prompt
    
    story_agent.update_role("supporting")
    prompt = story_agent._get_role_prompt()
    assert "配角" in prompt
    
    story_agent.update_role("observer")
    prompt = story_agent._get_role_prompt()
    assert "观察者" in prompt

@pytest.mark.asyncio
async def test_generate_response(story_agent):
    # 测试基本的响应生成
    response = await story_agent.generate_response("你好，请介绍一下这个故事。")
    assert isinstance(response, str)
    assert len(response) > 0

def test_update_role(story_agent):
    # 测试角色更新
    story_agent.update_role("protagonist")
    assert story_agent.role == "protagonist"
    
    story_agent.update_role("supporting")
    assert story_agent.role == "supporting"
    
    # 测试无效角色
    with pytest.raises(ValueError):
        story_agent.update_role("invalid_role")

@pytest.mark.asyncio
async def test_context_aware_response(story_agent, mock_knowledge_base):
    # 替换知识库为mock版本
    story_agent.knowledge_base = mock_knowledge_base
    
    # 测试上下文感知的响应
    response = await story_agent.generate_response("张三是谁？")
    assert "冒险家" in response.lower()
    
    response = await story_agent.generate_response("故事发生在哪里？")
    assert "森林" in response.lower()

@pytest.mark.asyncio
async def test_conversation_memory(story_agent):
    # 测试对话记忆功能
    first_response = await story_agent.generate_response("你好")
    second_response = await story_agent.generate_response("刚才说到哪里了？")
    
    # 验证第二个响应是否考虑了之前的对话
    assert len(story_agent.memory.chat_memory.messages) == 4  # 2个用户消息 + 2个AI响应
    assert "你好" in str(story_agent.memory.chat_memory.messages)

def test_tool_initialization(story_agent):
    # 测试工具初始化
    tools = story_agent.tools
    assert any(tool.name == "search_knowledge" for tool in tools)
    assert any(tool.name == "get_context" for tool in tools)

@pytest.mark.asyncio
async def test_error_handling(story_agent):
    # 测试错误处理
    with pytest.raises(Exception):
        await story_agent.generate_response("")  # 空输入
        
    with pytest.raises(Exception):
        await story_agent.generate_response("*" * 1000)  # 过长输入 