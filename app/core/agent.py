from typing import List, Dict, Optional
from pathlib import Path
import json
from datetime import datetime

from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.agents import Tool, AgentExecutor, LLMSingleActionAgent
from langchain.memory import ConversationBufferMemory
from langchain.prompts import StringPromptTemplate
from pydantic import BaseModel, Field

from app.api.llm import VolcengineLLM, get_llm
from app.models.schema import (
    NovelMetadata,
    Chapter,
    Character,
    Location,
    WorldState,
    UserRole,
    StoryProgress
)
from config.settings import settings
from app.core.knowledge import KnowledgeBase, StoryContext

class StoryAgent:
    def __init__(self, 
                 novel_id: str,
                 role: str = "observer"):
        self.novel_id = novel_id
        self.role = role
        self.llm = get_llm()
        self.knowledge_base = KnowledgeBase(novel_id)
        self.story_context = StoryContext(self.knowledge_base)
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # 初始化工具集
        self.tools = self._initialize_tools()
        
        # 初始化代理执行器
        self.agent_executor = self._initialize_agent()
        
    def _initialize_tools(self) -> List[Tool]:
        """初始化代理可用的工具集"""
        return [
            Tool(
                name="search_knowledge",
                func=self.knowledge_base.search,
                description="搜索小说相关的背景知识"
            ),
            Tool(
                name="get_context",
                func=self.story_context.get_relevant_knowledge,
                description="获取当前情节相关的上下文信息"
            )
        ]
        
    def _initialize_agent(self) -> AgentExecutor:
        """初始化代理执行器"""
        # TODO: 实现代理初始化逻辑
        pass
        
    def _get_role_prompt(self) -> str:
        """根据角色获取对应的提示词模板"""
        role_prompts = {
            "protagonist": """你现在扮演小说的主角。基于已知的情节发展和角色性格特征，
                            以第一人称视角回应用户的对话。注意保持角色性格的一致性。""",
            "supporting": """你现在扮演小说中的配角。根据角色在故事中的定位和特点，
                           以该角色的视角与用户互动。注意体现角色独特的说话方式和性格特征。""",
            "observer": """你现在是小说故事的观察者。你可以全局地了解故事发展，
                         并以旁观者的身份与用户讨论情节、人物和主题。"""
        }
        return role_prompts.get(self.role, role_prompts["observer"])
        
    async def generate_response(self, user_input: str) -> str:
        """生成对用户输入的回应"""
        # 更新上下文
        context = self.story_context.current_context
        
        # 构建提示词
        role_prompt = self._get_role_prompt()
        full_prompt = f"{role_prompt}\n\n当前上下文：{context}\n\n用户输入：{user_input}"
        
        # 调用代理执行器生成回应
        response = await self.agent_executor.arun(
            input=full_prompt,
            chat_history=self.memory.chat_memory.messages
        )
        
        # 更新对话历史
        self.memory.chat_memory.add_user_message(user_input)
        self.memory.chat_memory.add_ai_message(response)
        
        return response
        
    def update_role(self, new_role: str) -> None:
        """更新扮演的角色"""
        if new_role in ["protagonist", "supporting", "observer"]:
            self.role = new_role
        else:
            raise ValueError("Invalid role specified")
    
    def load_vector_store(self, vector_store_path: str) -> FAISS:
        """Load the vector store for the novel."""
        return FAISS.load_local(vector_store_path, self.embeddings)
    
    def initialize_session(
        self,
        novel_metadata: NovelMetadata,
        character_name: str,
        role_type: str
    ) -> StoryProgress:
        """Initialize a new story session for the user."""
        # Get character info
        character = next(
            (c for c in novel_metadata.main_characters if c.name == character_name),
            None
        )
        if not character:
            raise ValueError(f"Character {character_name} not found in novel")
        
        # Initialize user role
        user_role = UserRole(
            character_name=character_name,
            role_type=role_type,
            current_goals=[],  # Will be populated based on character's context
            inventory=[],
            relationships=character.relationships,
            dialogue_history=[]
        )
        
        # Initialize world state
        world_state = WorldState(
            current_chapter=1,
            current_location=novel_metadata.locations[0].name if novel_metadata.locations else "unknown",
            active_characters=[character_name],
            time_period="start",
            events_history=[]
        )
        
        # Create story progress
        progress = StoryProgress(
            session_id=f"{novel_metadata.title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_time=datetime.now(),
            current_world_state=world_state,
            user_role=user_role,
            completed_chapters=[],
            decision_points=[],
            generated_content={"images": [], "videos": []}
        )
        
        return progress
    
    def get_relevant_context(
        self,
        vector_store: FAISS,
        query: str,
        k: int = 3
    ) -> List[str]:
        """Retrieve relevant context from the novel based on the current situation."""
        results = vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in results]
    
    def update_world_state(
        self,
        progress: StoryProgress,
        user_action: str
    ) -> WorldState:
        """Update the world state based on user action."""
        # Get relevant context
        context_query = f"""
        Character: {progress.user_role.character_name}
        Current location: {progress.current_world_state.current_location}
        Action: {user_action}
        """
        
        # Generate world state update using LLM
        messages = [
            {"role": "system", "content": "You are a story manager that updates the world state based on character actions."},
            {"role": "user", "content": f"Based on the following context and action, suggest updates to the world state:\n\n{context_query}"}
        ]
        
        response = self.llm.chat_completion(messages, temperature=0.3)
        updates = json.loads(response["choices"][0]["message"]["content"])
        
        # Update world state
        progress.current_world_state.update(updates)
        return progress.current_world_state
    
    def generate_response(
        self,
        progress: StoryProgress,
        user_input: str,
        vector_store: FAISS
    ) -> Dict:
        """Generate in-character response and updates."""
        # Get relevant context
        context = self.get_relevant_context(
            vector_store,
            f"{progress.current_world_state.current_location} {user_input}"
        )
        
        # Generate character response
        response = self.llm.generate_character_response(
            character_info={
                "name": progress.user_role.character_name,
                "traits": progress.user_role.current_goals,
                "background": "Character background here"  # This should come from metadata
            },
            context="\n".join(context),
            user_input=user_input,
            dialogue_history=progress.user_role.dialogue_history
        )
        
        # Update dialogue history
        progress.user_role.dialogue_history.append({
            "is_user": True,
            "text": user_input,
            "timestamp": datetime.now()
        })
        progress.user_role.dialogue_history.append({
            "is_user": False,
            "text": response,
            "timestamp": datetime.now()
        })
        
        # Update world state
        world_state = self.update_world_state(progress, user_input)
        
        return {
            "response": response,
            "world_state": world_state,
            "context_used": context
        }
    
    def check_story_progression(
        self,
        progress: StoryProgress,
        novel_metadata: NovelMetadata
    ) -> Dict:
        """Check if story should progress to next chapter or present decision points."""
        current_chapter = progress.current_world_state.current_chapter
        
        if current_chapter >= novel_metadata.total_chapters:
            return {"status": "completed", "message": "Story has reached its conclusion"}
        
        # Check if current chapter goals are met
        chapter_completion_check = self.llm.chat_completion([
            {"role": "system", "content": "You are a story progression checker that determines if chapter goals are met."},
            {"role": "user", "content": f"Check if the current chapter {current_chapter} goals are met based on the world state and events:\n{json.dumps(progress.current_world_state.dict())}"}
        ])
        
        should_progress = json.loads(chapter_completion_check["choices"][0]["message"]["content"])["should_progress"]
        
        if should_progress:
            progress.current_world_state.current_chapter += 1
            progress.completed_chapters.append(current_chapter)
            return {"status": "progressed", "new_chapter": current_chapter + 1}
        
        return {"status": "in_progress"} 