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

from agent.core.agent_coordinator import AgentCoordinator
from agent.core.document_agent import DocumentAgent
from agent.core.knowledge_agent import KnowledgeAgent
from agent.core.interaction_agent import InteractionAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置信息
DATA_DIR = Path("./data")
DEFAULT_LLM_MODEL = "deepseek-chat"

def init_session_state():
    """初始化会话状态"""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = False
        st.session_state.coordinator = None
        st.session_state.document_id = None
        st.session_state.document_info = None
        st.session_state.character_name = None
        st.session_state.current_chapter = 1
        st.session_state.knowledge_base = None
        st.session_state.current_scene = None
        st.session_state.api_keys = {
            'llm_api_key': os.environ.get('DEEPSEEK_API_KEY', ''),
            'image_access_key_id': os.environ.get('IMAGE_ACCESS_KEY_ID', ''),
            'image_secret_key': os.environ.get('IMAGE_SECRET_KEY', '')
        }

def setup_coordinator():
    """设置代理协调器"""
    if st.session_state.coordinator is None:
        st.session_state.coordinator = AgentCoordinator()
        
        # 配置参数
        config = {
            'data_dir': str(DATA_DIR),
            'llm_api_key': st.session_state.api_keys['llm_api_key'],
            'llm_model': DEFAULT_LLM_MODEL,
            'supported_languages': ['zh', 'en']
        }
        
        # 注册代理
        document_agent = DocumentAgent(config)
        knowledge_agent = KnowledgeAgent(config)
        interaction_agent = InteractionAgent(config)
        
        st.session_state.coordinator.register_agent('document', document_agent)
        st.session_state.coordinator.register_agent('knowledge', knowledge_agent)
        st.session_state.coordinator.register_agent('interaction', interaction_agent)
        
        # 初始化所有代理
        st.session_state.coordinator.initialize_all_agents()
        
        st.session_state.initialized = True

def show_api_settings():
    """显示API设置页面"""
    st.title("API设置")
    
    with st.form("api_settings_form"):
        llm_api_key = st.text_input("DeepSeek API Key", 
            value=st.session_state.api_keys.get('llm_api_key', ''),
            type="password"
        )
        
        # 更新文生图API设置为Access Key ID和Secret Access Key
        st.subheader("即梦文生图API设置")
        image_access_key_id = st.text_input("Access Key ID", 
            value=st.session_state.api_keys.get('image_access_key_id', ''),
            type="password"
        )
        
        image_secret_key = st.text_input("Secret Access Key", 
            value=st.session_state.api_keys.get('image_secret_key', ''),
            type="password"
        )
        
        submitted = st.form_submit_button("保存设置")
        
        if submitted:
            st.session_state.api_keys['llm_api_key'] = llm_api_key
            st.session_state.api_keys['image_access_key_id'] = image_access_key_id
            st.session_state.api_keys['image_secret_key'] = image_secret_key
            
            # 如果存在协调器，更新API密钥
            if st.session_state.coordinator:
                for agent_name in st.session_state.coordinator.agents:
                    agent = st.session_state.coordinator.agents[agent_name]
                    if hasattr(agent, 'client'):
                        agent.client.api_key = llm_api_key
            
            st.success("设置已保存")
            
            # 重新设置协调器
            st.session_state.coordinator = None
            setup_coordinator()

def upload_document():
    """上传文档页面"""
    st.title("上传小说文档")
    
    # 文件上传
    uploaded_file = st.file_uploader("选择小说文件", type=["txt"])
    
    # 基本设置
    language = st.selectbox("选择语言", ["中文", "英文"], index=0)
    lang_code = "zh" if language == "中文" else "en"
    
    content_percentage = st.slider("处理文档百分比", 10, 100, 100, 5)
    
    if uploaded_file is not None:
        if st.button("处理文档"):
            with st.spinner("正在处理文档..."):
                # 保存上传的文件
                temp_file_path = Path(DATA_DIR) / "temp" / uploaded_file.name
                temp_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 处理文档
                context = {
                    'file_path': str(temp_file_path),
                    'language': lang_code,
                    'content_percentage': content_percentage
                }
                
                result = st.session_state.coordinator.execute_agent('document', context)
                
                if result.get('status') == 'success':
                    st.session_state.document_id = result.get('document_info', {}).get('document_id')
                    st.session_state.document_info = result.get('document_info', {})
                    
                    st.success(f"文档处理成功: {st.session_state.document_id}")
                    
                    # 提取知识
                    with st.spinner("正在提取知识..."):
                        knowledge_context = {
                            'document_info': st.session_state.document_info
                        }
                        
                        knowledge_result = st.session_state.coordinator.execute_agent('knowledge', knowledge_context)
                        
                        if knowledge_result.get('status') == 'success':
                            st.session_state.knowledge_base = knowledge_result.get('knowledge_base')
                            st.success("知识提取成功")
                        else:
                            st.error(f"知识提取失败: {knowledge_result.get('message')}")
                else:
                    st.error(f"文档处理失败: {result.get('message')}")

def select_character():
    """选择角色页面"""
    st.title("选择角色")
    
    if not st.session_state.document_id or not st.session_state.knowledge_base:
        st.warning("请先上传并处理文档")
        return
    
    # 显示文档信息
    st.subheader("文档信息")
    st.write(f"标题: {st.session_state.document_info.get('title')}")
    st.write(f"总章节: {st.session_state.document_info.get('total_chapters')}")
    
    # 显示角色列表
    st.subheader("可选角色")
    
    characters = st.session_state.knowledge_base.get('characters', {})
    if not characters:
        st.warning("未找到角色信息")
        return
        
    # 按重要性排序
    sorted_chars = sorted(
        characters.items(), 
        key=lambda x: x[1].get('importance', 0), 
        reverse=True
    )
    
    for name, info in sorted_chars:
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if st.button(f"选择 {name}", key=f"btn_{name}"):
                st.session_state.character_name = name
                
                # 启动交互
                start_context = {
                    'action': 'start',
                    'document_id': st.session_state.document_id,
                    'character_name': name,
                    'chapter': st.session_state.current_chapter,
                    'knowledge_base': st.session_state.knowledge_base
                }
                
                with st.spinner(f"正在初始化 {name} 的故事..."):
                    result = st.session_state.coordinator.execute_agent('interaction', start_context)
                    
                    if result.get('status') == 'success':
                        st.session_state.current_scene = result.get('scene')
                        st.rerun()
                    else:
                        st.error(f"启动交互失败: {result.get('message')}")
        
        with col2:
            # 显示角色描述
            st.markdown(f"**{name}**")
            st.write(info.get('description', ''))
            st.write(f"出场章节: {', '.join(str(ch) for ch in info.get('appearances', []))}")
            
            # 分隔符
            st.markdown("---")

def interaction_interface():
    """交互界面"""
    if not st.session_state.character_name or not st.session_state.current_scene:
        return
    
    # 设置页面
    st.title(f"《{st.session_state.document_info.get('title')}》互动体验")
    
    # 添加章节标题信息
    chapter_info = ""
    if st.session_state.document_info and st.session_state.document_info.get('chapter_titles'):
        chapter_titles = st.session_state.document_info.get('chapter_titles', {})
        current_chapter_str = str(st.session_state.current_chapter)
        if current_chapter_str in chapter_titles:
            chapter_info = f" - {chapter_titles[current_chapter_str]}"
    
    st.subheader(f"角色: {st.session_state.character_name} | 第 {st.session_state.current_chapter} 章{chapter_info}")
    
    # 顶部控制按钮
    col1, col2, col3, col4 = st.columns(4)
    
    # 在执行下一章时清除搜索结果和记忆状态
    def clear_session_cache():
        if 'search_results' in st.session_state:
            del st.session_state.search_results
        if 'image_url' in st.session_state:
            st.session_state.image_url = None
        if 'remote_url' in st.session_state:
            st.session_state.remote_url = None

    with col1:
        if st.button("停止交互"):
            with st.spinner("正在停止交互..."):
                result = st.session_state.coordinator.execute_agent('interaction', {'action': 'stop'})
                if result.get('status') == 'success':
                    st.session_state.character_name = None
                    st.session_state.current_scene = None
                    clear_session_cache()
                    st.rerun()
    
    with col2:
        if st.button("下一章"):
            with st.spinner("正在进入下一章..."):
                result = st.session_state.coordinator.execute_agent('interaction', {'action': 'next_chapter'})
                if result.get('status') == 'success':
                    # 更新当前章节编号
                    st.session_state.current_chapter += 1
                    st.session_state.current_scene = result.get('scene')
                    clear_session_cache()
                    st.rerun()
                else:
                    st.error(f"进入下一章失败: {result.get('message')}")
    
    with col3:
        total_chapters = st.session_state.document_info.get('total_chapters', 1)
        # 确保章节选择控件的值与当前章节同步
        target_chapter = st.number_input("跳转到章节", 1, total_chapters, st.session_state.current_chapter, key=f"chapter_select_{st.session_state.current_chapter}")
    
    with col4:
        if st.button("跳转"):
            with st.spinner(f"正在跳转到第{target_chapter}章..."):
                result = st.session_state.coordinator.execute_agent('interaction', {
                    'action': 'jump_to',
                    'chapter': target_chapter
                })
                if result.get('status') == 'success':
                    st.session_state.current_chapter = target_chapter
                    st.session_state.current_scene = result.get('scene')
                    
                    # 清除之前的图像
                    if 'image_url' in st.session_state:
                        st.session_state.image_url = None
                    if 'remote_url' in st.session_state:
                        st.session_state.remote_url = None
                        
                    st.rerun()
                else:
                    st.error(f"跳转失败: {result.get('message')}")
    
    # 添加故事搜索功能
    st.sidebar.subheader("故事信息搜索")
    query = st.sidebar.text_input("搜索故事中的人物、事件、地点等", key="story_search_input")
    if st.sidebar.button("搜索", key="story_search_button"):
        if query:
            search_status = st.sidebar.empty()
            search_status.info("正在搜索...")
            
            result = st.session_state.coordinator.execute_agent('interaction', {
                'action': 'search_info',
                'query': query
            })
            
            if result.get('status') == 'success':
                st.session_state.search_results = result.get('results', [])
                search_status.empty()
            else:
                st.sidebar.error(f"搜索失败: {result.get('message')}")
                st.session_state.search_results = []
                search_status.empty()
        else:
            st.sidebar.warning("请输入搜索内容")
    
    # 显示搜索结果
    if hasattr(st.session_state, 'search_results') and st.session_state.search_results:
        st.sidebar.subheader(f"搜索结果 ({len(st.session_state.search_results)})")
        for i, result in enumerate(st.session_state.search_results):
            with st.sidebar.expander(f"{i+1}. {result['source']}"):
                st.write(result['content'])
                st.caption(f"类型: {result['type']} | 相关度: {result['relevance']:.2f}")
    
    # 主界面显示当前场景
    scene = st.session_state.current_scene
    
    # 主要内容分区
    main_col, context_col = st.columns([7, 3])
    
    with main_col:
        # 显示图像
        image_container = st.container()
        with image_container:
            # 显示生成的图像
            if 'image_url' in st.session_state and st.session_state.image_url and os.path.exists(st.session_state.image_url):
                st.image(st.session_state.image_url)
            elif 'remote_url' in st.session_state and st.session_state.remote_url and st.session_state.remote_url.startswith('http'):
                st.image(st.session_state.remote_url)
        
        # 显示场景描述
        st.markdown(f"## 场景")
        narrative = scene.get('narrative', '')
        st.markdown(f"{narrative}")
        
        # 显示交互点
        st.markdown(f"## 互动")
        st.markdown(f"_{scene.get('interaction_point', '')}_")
        
        if 'context_hint' in scene and scene['context_hint']:
            with st.expander("提示"):
                st.markdown(f"{scene.get('context_hint', '')}")
        
        # 用户输入
        user_input = st.text_area("你的选择", height=100, key="user_input_area")
        
        # 提交选择
        if st.button("确认", type="primary"):
            if user_input:
                with st.spinner("思考中..."):
                    # 处理用户选择
                    result = st.session_state.coordinator.execute_agent('interaction', {
                        'action': 'continue',
                        'user_input': user_input
                    })
                    
                    # 如果检测到偏离
                    if result.get('status') == 'warning':
                        divergence = result.get('divergence', {})
                        st.warning(f"检测到故事偏离: {divergence.get('description')}")
                        st.warning(f"偏离等级: {divergence.get('level')}/5")
                        
                        if divergence.get('level', 0) >= 4:
                            # 高偏离度，显示确认选项
                            st.error("这个选择将导致故事严重偏离原定情节，确定要继续吗？")
                            if st.button("继续", key="continue_divergence"):
                                # 继续处理
                                result = st.session_state.coordinator.execute_agent('interaction', {
                                    'action': 'continue',
                                    'user_input': user_input,
                                    'force_continue': True
                                })
                                
                                if result.get('status') == 'success':
                                    st.session_state.current_scene = result.get('scene')
                                    st.rerun()
                    
                    elif result.get('status') == 'success':
                        st.session_state.current_scene = result.get('scene')
                        
                        # 检查是否应该进入下一章
                        if result.get('should_proceed_chapter'):
                            st.info("已达到章节结尾，可以进入下一章")
                            
                        st.rerun()
                    else:
                        st.error(f"处理选择失败: {result.get('message')}")
    
    # 右侧情境上下文列
    with context_col:
        # 跨章节记忆区
        with st.expander("记忆与线索", expanded=True):
            # 获取记忆检索
            memory_status = st.empty()
            memory_status.info("加载记忆中...")
            
            memory_result = st.session_state.coordinator.execute_agent('interaction', {
                'action': 'search_info',
                'query': scene.get('narrative', '')[:100]  # 使用场景描述前100个字符作为查询
            })
            
            memory_status.empty()
            
            if memory_result.get('status') == 'success':
                memories = memory_result.get('results', [])
                
                # 显示主要线索
                clues = [m for m in memories if m.get('type') == 'key_clue']
                if clues:
                    st.markdown("#### 关键线索")
                    for clue in clues[:3]:
                        st.markdown(f"- {clue['content']}")
                
                # 显示章节摘要
                summaries = [m for m in memories if m.get('type') == 'chapter_summary']
                if summaries and len(summaries) > 0:
                    with st.expander("上一章节回顾"):
                        st.markdown(summaries[0]['content'])
        
        # 情感状态
        with st.expander("情感状态", expanded=True):
            emotion_state = scene.get('emotion_state', {})
            if isinstance(emotion_state, dict):
                for character, emotion in emotion_state.items():
                    st.markdown(f"**{character}**: {emotion}")
            else:
                st.markdown(emotion_state)
        
        # 当前进度与即将发生事件
        with st.expander("剧情进度", expanded=True):
            progress_info = scene.get('progress_info', {})
            current_progress = progress_info.get('progress', 0)
            
            # 如果用户点击了"下一章"按钮显示的提示，说明当前章节已完成，进度应该为100%
            chapter_complete = False
            for i in range(len(st.session_state.get('_messages', []))-1, -1, -1):
                msg = st.session_state.get('_messages', [])[i]
                if isinstance(msg, dict) and msg.get('content') == "已达到章节结尾，可以进入下一章":
                    chapter_complete = True
                    break
            
            if chapter_complete:
                current_progress = 100
            
            # 进度条
            st.progress(current_progress / 100)
            st.markdown(f"**进度**: {current_progress}%")
            
            # 当前场景
            st.markdown(f"**当前场景**: {progress_info.get('current_scene', '')}")
            
            # 章节状态提示
            if current_progress >= 95:
                st.success("当前章节即将完成，可以准备进入下一章")
            
            # 即将发生的事件
            if 'next_key_events' in progress_info and progress_info['next_key_events']:
                st.markdown("**即将发生**:")
                for event in progress_info.get('next_key_events', []):
                    st.markdown(f"- {event}")
                    
        # 图像生成区
        with st.expander("生成场景图像"):
            # 图像风格选项
            image_style = st.selectbox(
                "图像风格",
                options=["realistic", "anime", "painting", "sketch", "3d"],
                index=0,
                key="image_style"
            )
            
            # 图像尺寸选项
            image_size = st.selectbox(
                "图像尺寸",
                options=["512x512", "768x768", "1024x1024"],
                index=0,
                key="image_size"
            )
            
            # 生成图像按钮
            if st.button("生成图像", key="gen_image_btn"):
                # 验证API密钥是否已设置
                access_key_id = st.session_state.api_keys.get('image_access_key_id')
                secret_key = st.session_state.api_keys.get('image_secret_key')
                
                if not access_key_id or not secret_key:
                    st.warning("请先在'API设置'页面设置即梦文生图API的Access Key ID和Secret Access Key。")
                else:
                    with st.spinner("正在生成图像..."):
                        # 创建交互代理实例
                        interaction_agent = st.session_state.coordinator.agents.get('interaction')
                        
                        # 生成图像
                        image_result = interaction_agent.generate_image_from_scene(
                            scene, 
                            access_key_id=access_key_id,
                            secret_key=secret_key,
                            style=image_style,
                            size=image_size
                        )
                        
                        if image_result.get('status') == 'success':
                            # 如果有图像路径（本地文件）或远程URL，显示图像
                            image_url = image_result.get('image_url')
                            remote_url = image_result.get('remote_url', '')
                            
                            if image_url and os.path.exists(image_url):
                                # 保存图像URL到会话状态
                                st.session_state.image_url = image_url
                                st.session_state.remote_url = None
                                st.success("图像生成成功！")
                                st.rerun()
                            elif remote_url and remote_url.startswith('http'):
                                # 保存远程URL到会话状态
                                st.session_state.remote_url = remote_url
                                st.session_state.image_url = None
                                st.success("图像生成成功！")
                                st.rerun()
                            else:
                                st.error("图像生成成功，但无法获取图像路径或URL。")
                        else:
                            error_msg = image_result.get('message', '')
                            st.error(f"生成图像失败: {error_msg}")
                            if "SignatureDoesNotMatch" in error_msg:
                                st.error("API签名验证失败，请检查您的Access Key ID和Secret Access Key是否正确输入，确保没有多余的空格或特殊字符。")
                            elif "Post Text Risk Not Pass" in error_msg or "Risk" in error_msg:
                                st.error("提示词被内容审核系统判定存在风险，系统已自动尝试处理，但仍未通过。请尝试修改场景描述，避免敏感内容。")
                                original_prompt = image_result.get('original_prompt', '')
                                sanitized_prompt = image_result.get('sanitized_prompt', '')
                                if original_prompt and sanitized_prompt:
                                    st.info(f"原始提示词: {original_prompt}")
                                    st.info(f"处理后提示词: {sanitized_prompt}")
                            st.info("提示：请确保即梦API密钥有效并且有足够的配额。图像生成需要使用专门的文生图服务。")

def main():
    """主函数"""
    st.set_page_config(
        page_title="沉浸式小说体验",
        page_icon="📚",
        layout="wide"
    )
    
    # 初始化
    init_session_state()
    setup_coordinator()
    
    # 侧边栏导航
    st.sidebar.title("沉浸式小说体验")
    
    page = st.sidebar.radio(
        "导航", 
        ["API设置", "上传文档", "选择角色", "交互页面"]
    )
    
    # 渲染页面
    if page == "API设置":
        show_api_settings()
    elif page == "上传文档":
        upload_document()
    elif page == "选择角色":
        select_character()
    elif page == "交互页面":
        interaction_interface()

if __name__ == "__main__":
    main() 