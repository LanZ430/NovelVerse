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
from agent.core.interaction import InteractionAgent

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
            'image_secret_key': os.environ.get('IMAGE_SECRET_KEY', ''),
            'voice_app_id': os.environ.get('VOICE_APP_ID', ''),
            'voice_token': os.environ.get('VOICE_TOKEN', '')
        }
        # 语音功能状态
        st.session_state.voice_enabled = False
        st.session_state.current_dialogues = []
        st.session_state.audio_autoplay = False

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
        
        # 添加语音服务配置
        if st.session_state.voice_enabled:
            voice_app_id = st.session_state.api_keys.get('voice_app_id')
            voice_token = st.session_state.api_keys.get('voice_token')
            if voice_app_id and voice_token:
                config['voice_app_id'] = voice_app_id
                config['voice_token'] = voice_token
                print(f"[DEBUG][setup_coordinator] 添加语音配置: voice_app_id={voice_app_id[:5] if voice_app_id else None}***, voice_token={'YES' if voice_token else 'NO'}")
                logger.info(f"[DEBUG][setup_coordinator] 添加语音配置: voice_app_id={voice_app_id[:5] if voice_app_id else None}***, voice_token={'YES' if voice_token else 'NO'}")
        
        # 注册代理
        document_agent = DocumentAgent(config)
        knowledge_agent = KnowledgeAgent(config)
        interaction_agent = InteractionAgent(config)
        
        st.session_state.coordinator.register_agent('document', document_agent)
        st.session_state.coordinator.register_agent('knowledge', knowledge_agent)
        st.session_state.coordinator.register_agent('interaction', interaction_agent)
        
        # 初始化所有代理
        st.session_state.coordinator.initialize_all_agents()
        
        # 如果启用了语音功能且设置了AppID，再次确保语音服务初始化
        if st.session_state.voice_enabled and st.session_state.api_keys.get('voice_app_id'):
            interaction_agent = st.session_state.coordinator.agents.get('interaction')
            if interaction_agent:
                voice_app_id = st.session_state.api_keys.get('voice_app_id')
                voice_token = st.session_state.api_keys.get('voice_token')
                logger.info(f"[DEBUG][setup_coordinator] 确认语音服务初始化: app_id={voice_app_id[:5] if voice_app_id else None}***")
                voice_result = interaction_agent.set_voice_app_id(voice_app_id, voice_token)
                logger.info(f"[DEBUG][setup_coordinator] 语音服务初始化结果: {voice_result.get('status')}")
                
                # 打印详细信息以便排错
                try:
                    auth_info = interaction_agent.interaction_agent.voice_service.debug_auth_info()
                    logger.info(f"[DEBUG][setup_coordinator] 语音服务认证信息: {auth_info}")
                except:
                    logger.warning("[DEBUG][setup_coordinator] 无法获取语音服务认证信息")
                    
                # 测试语音服务
                try:
                    test_result = interaction_agent.test_voice_service()
                    logger.info(f"[DEBUG][setup_coordinator] 语音服务测试结果: {test_result['status']} - {test_result['message']}")
                except:
                    logger.warning("[DEBUG][setup_coordinator] 语音服务测试失败")
                    
        return st.session_state.coordinator
    
    return st.session_state.coordinator

def show_api_settings():
    """显示API设置页面"""
    st.title("API设置")
    
    # API设置表单
    with st.form("api_settings_form"):
        # LLM API设置
        st.subheader("LLM API设置")
        llm_api_key = st.text_input("API Key", 
            value=st.session_state.api_keys.get('llm_api_key', ''),
                                  type="password",
                                  help="输入DeepSeek或其他LLM服务的API密钥")
        
        # 图像生成API设置
        st.subheader("火山引擎图像生成API设置")
        image_access_key_id = st.text_input("AccessKeyId", 
            value=st.session_state.api_keys.get('image_access_key_id', ''),
                                          help="输入火山引擎的AccessKey ID")
        
        image_secret_key = st.text_input("SecretKey", 
            value=st.session_state.api_keys.get('image_secret_key', ''),
                                       type="password",
                                       help="输入火山引擎的Secret Key")

        # 语音合成设置
        st.subheader("语音合成设置")
        voice_enabled = st.checkbox("启用语音功能", value=st.session_state.voice_enabled, 
                                  help="启用后，系统将为场景中的对话生成语音")
        audio_autoplay = st.checkbox("自动播放音频", value=st.session_state.audio_autoplay,
                                   help="启用后，当生成新场景时会自动播放对话语音")
        
        voice_app_id = st.text_input("火山引擎语音合成AppID", 
                                    value=st.session_state.api_keys.get('voice_app_id', ''),
                                    help="输入火山引擎语音合成的AppID，用于生成场景对话的语音")
        
        voice_token = st.text_input("火山引擎语音合成Token", 
                                   value=st.session_state.api_keys.get('voice_token', ''),
                                   type="password",
                                   help="输入火山引擎语音合成的access_token，用于API认证")
        
        # 添加Token格式说明
        st.info("""
        **重要提示**: 
        
        1. 语音合成服务需要使用火山引擎控制台提供的**access_token**，而非API Key。
        2. 这个token需要从火山引擎控制台获取，是用于HTTP/WebSocket请求的认证凭证。
        3. 请注意区分：
           - 请求体(JSON)中的"token"字段可以是任意非空字符串，这只是一个占位符
           - 真正的认证发生在HTTP头部的"Authorization"字段，格式为"Bearer; {token}"（注意分号后有空格）
        4. 在此处输入的是真正的认证token，系统会自动将其放入Authorization头部
        5. 正确的token通常是一个较长的字符串，JWT格式的token通常以eyJ开头
        
        如果您收到错误"requested resource not granted"或"资源访问权限不足"，这表示：
        1. 您的账号没有权限访问所请求的语音资源（音色）
        2. 您需要在火山引擎控制台中开通相应的语音合成服务和权限
        3. 系统将自动尝试使用免费音色（如BV001_streaming）作为替代
        
        如果您收到错误"refresh authenticator storage"或"invalid response status code: 400/401/403"，
        说明您使用的token可能不正确。请确保从火山引擎控制台获取正确的access_token。
        """)
        
        # 保存按钮
        submitted = st.form_submit_button("保存所有设置")
    
    # 表单外的测试按钮
    if st.button("测试语音服务"):
        test_voice_service()
        
    if st.button("测试令牌格式"):
        test_token_format()
        
    if st.button("使用免费音色测试"):
        test_free_voice()
    
    # 处理保存操作    
        if submitted:
        # 保存所有API密钥
            st.session_state.api_keys['llm_api_key'] = llm_api_key
            st.session_state.api_keys['image_access_key_id'] = image_access_key_id
            st.session_state.api_keys['image_secret_key'] = image_secret_key
        st.session_state.api_keys['voice_app_id'] = voice_app_id
        st.session_state.api_keys['voice_token'] = voice_token
        
        # 保存语音设置
        st.session_state.voice_enabled = voice_enabled
        st.session_state.audio_autoplay = audio_autoplay
        
        print(f"[DEBUG][show_api_settings] 更新语音设置: enabled={voice_enabled}, app_id={voice_app_id[:5] if voice_app_id else None}***, token={'YES' if voice_token else 'NO'}")
        logger.info(f"[DEBUG][show_api_settings] 更新语音设置: enabled={voice_enabled}, app_id={voice_app_id[:5] if voice_app_id else None}***, token={'YES' if voice_token else 'NO'}")
            
            # 如果存在协调器，更新API密钥
            if st.session_state.coordinator:
            # 更新LLM API Key
                for agent_name in st.session_state.coordinator.agents:
                    agent = st.session_state.coordinator.agents[agent_name]
                    if hasattr(agent, 'client'):
                        agent.client.api_key = llm_api_key
            
            # 更新语音服务
            if voice_enabled and voice_app_id:
                interaction_agent = st.session_state.coordinator.agents.get('interaction')
                if interaction_agent:
                    voice_result = interaction_agent.set_voice_app_id(voice_app_id, voice_token)
                    if voice_result.get('status') == 'success':
                        st.success("设置已保存，语音服务初始化成功")
                    else:
                        st.warning(f"设置已保存，但语音服务初始化失败: {voice_result.get('message')}")
                        return
        
        st.success("所有设置已保存")

def test_voice_service():
    """测试语音服务配置"""
    if not st.session_state.coordinator:
        st.error("请先设置API密钥")
        return
    
    voice_app_id = st.session_state.api_keys.get('voice_app_id')
    voice_token = st.session_state.api_keys.get('voice_token')
    
    if not voice_app_id or not voice_token:
        st.error("请先设置语音服务AppID和Token")
        return
    
    with st.spinner("正在测试语音服务..."):
        try:
            # 获取交互代理
            interaction_adapter = st.session_state.coordinator.agents.get('interaction')
            if not interaction_adapter:
                st.error("交互代理未初始化")
                return
            
            # 验证Token格式
            if interaction_adapter.interaction_agent and interaction_adapter.interaction_agent.voice_service:
                validation_result = interaction_adapter.interaction_agent.voice_service.validate_token()
                if validation_result["status"] != "success":
                    st.warning("您的Token可能不正确，测试可能会失败。请查看下方Token验证结果。")
                    st.json(validation_result)
                    
                    if len(voice_token) < 10:
                        st.error("""
                        您的Token长度异常短，这可能不是有效的Token。
                        
                        火山引擎语音合成需要使用专门的access_token，而非API Key或其他凭证。
                        正确的Token通常是一个较长的字符串，JWT格式的Token通常以eyJ开头。
                        
                        请登录火山引擎控制台获取正确的Token: https://console.volcengine.com/
                        """)
            
            # 确保语音服务初始化
            result = interaction_adapter.test_voice_service()
            
            if result["status"] == "success":
                st.success(f"语音服务测试成功: {result['message']}")
                # 显示音频
                if "audio_path" in result:
                    st.audio(result["audio_path"])
            else:
                st.error(f"语音服务测试失败: {result['message']}")
                
                # 检查是否是401错误
                if "details" in result and "error_data" in result["details"]:
                    error_data = result["details"]["error_data"]
                    if isinstance(error_data, dict) and error_data.get("code") == 3001 and "load grant" in error_data.get("message", ""):
                        st.error("""
                        ### 认证失败: Token无效或格式错误
                        
                        您使用的可能不是正确的Token。火山引擎语音合成需要使用专门的access_token，而非API Key或其他凭证。
                        
                        请按照以下步骤获取正确的Token:
                        1. 登录[火山引擎控制台](https://console.volcengine.com/)
                        2. 进入语音服务页面
                        3. 在应用管理中找到您的应用
                        4. 获取应用的access_token
                        
                        如果您已有正确的Token，请确保完整复制，不要漏掉任何字符。
                        """)
                
                if "auth_info" in result:
                    st.json(result["auth_info"])
                    
                    # 额外的令牌测试
                    if interaction_adapter.interaction_agent and interaction_adapter.interaction_agent.voice_service:
                        token_test = interaction_adapter.interaction_agent.voice_service.test_token()
                        st.subheader("令牌测试结果")
                        st.json(token_test)
        except Exception as e:
            st.error(f"测试过程发生错误: {str(e)}")
            logger.exception("测试语音服务时发生错误")

def test_token_format():
    """测试令牌格式"""
    if not st.session_state.coordinator:
        st.error("请先设置API密钥")
        return
    
    voice_token = st.session_state.api_keys.get('voice_token')
    
    if not voice_token:
        st.error("请先设置语音服务Token")
        return
    
    # 显示原始令牌信息
    st.subheader("令牌信息")
    token_info = {
        "原始令牌长度": len(voice_token),
        "原始令牌前5位": voice_token[:5] + "***" if len(voice_token) > 5 else voice_token,
        "是否包含Bearer前缀": voice_token.startswith("Bearer"),
        "是否包含分号": ";" in voice_token,
        "是否包含空格": " " in voice_token,
        "是否包含换行符": "\n" in voice_token or "\r" in voice_token
    }
    st.json(token_info)
    
    # 清理令牌
    clean_token = voice_token
    if clean_token.startswith("Bearer"):
        clean_token = clean_token.replace("Bearer", "").strip()
        if clean_token.startswith(";"):
            clean_token = clean_token[1:].strip()
    
    # 显示清理后的令牌信息
    st.subheader("清理后的令牌信息")
    clean_info = {
        "清理后令牌长度": len(clean_token),
        "清理后令牌前5位": clean_token[:5] + "***" if len(clean_token) > 5 else clean_token,
        "正确的认证头格式": f"Bearer; {clean_token[:5]}***" if len(clean_token) > 5 else f"Bearer; {clean_token}"
    }
    st.json(clean_info)
    
    # 提供Token格式指南
    st.subheader("Token格式指南")
    st.markdown("""
    ### 火山引擎语音合成Token说明
    
    1. 语音合成服务需要使用火山引擎控制台提供的**access_token**，而非API Key
    2. 正确的Token通常是一个较长的字符串，JWT格式的Token通常以`eyJ`开头
    3. 获取Token的步骤:
       - 登录[火山引擎控制台](https://console.volcengine.com/)
       - 进入语音服务页面
       - 在应用管理中找到您的应用
       - 获取应用的access_token
    
    如果您使用的是API Key或其他凭证，将无法正常使用语音服务。
    """)
    
    # 尝试更新令牌
    try:
        interaction_adapter = st.session_state.coordinator.agents.get('interaction')
        if interaction_adapter and interaction_adapter.interaction_agent and interaction_adapter.interaction_agent.voice_service:
            # 更新令牌
            interaction_adapter.interaction_agent.voice_service.set_token(clean_token)
            st.success("已更新为清理后的令牌格式")
            
            # 验证令牌格式
            validation_result = interaction_adapter.interaction_agent.voice_service.validate_token()
            st.subheader("令牌格式验证结果")
            st.json(validation_result)
            
            if validation_result["status"] != "success":
                st.warning("您的Token可能不正确。请确保使用的是火山引擎控制台提供的access_token，而非API Key。")
            
            # 测试令牌
            token_test = interaction_adapter.interaction_agent.voice_service.test_token()
            st.subheader("令牌测试结果")
            st.json(token_test)
    except Exception as e:
        st.error(f"更新令牌时发生错误: {str(e)}")
        logger.exception("更新令牌时发生错误")

def test_free_voice():
    """使用免费音色测试语音服务"""
    if not st.session_state.coordinator:
        st.error("请先设置API密钥")
        return
    
    voice_app_id = st.session_state.api_keys.get('voice_app_id')
    voice_token = st.session_state.api_keys.get('voice_token')
    
    if not voice_app_id or not voice_token:
        st.error("请先设置语音服务AppID和Token")
        return
    
    with st.spinner("正在使用免费音色测试..."):
        try:
            # 获取交互代理
            interaction_adapter = st.session_state.coordinator.agents.get('interaction')
            if not interaction_adapter:
                st.error("交互代理未初始化")
                return
            
            # 确保语音服务初始化
            if not interaction_adapter.interaction_agent or not interaction_adapter.interaction_agent.voice_service:
                st.error("语音服务未初始化")
                return
                
            # 使用免费音色生成测试语音
            audio_path = interaction_adapter.interaction_agent.voice_service.generate_speech(
                text="这是使用免费音色的测试语音",
                voice_type="BV001_streaming",
                return_path=True
            )
            
            if audio_path:
                st.success("免费音色测试成功！")
                st.audio(audio_path)
            else:
                st.error("免费音色测试失败")
                
                # 获取详细的错误信息
                token_test = interaction_adapter.interaction_agent.voice_service.test_token()
                st.subheader("令牌测试结果")
                st.json(token_test)
        except Exception as e:
            st.error(f"测试过程发生错误: {str(e)}")
            logger.exception("测试免费音色时发生错误")

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
    print("[DEBUG][app.py select_character] auto_voice:", st.session_state.voice_enabled)
    
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
                
                # 获取API密钥
                access_key_id = st.session_state.api_keys.get('image_access_key_id')
                secret_key = st.session_state.api_keys.get('image_secret_key')
                
                # 检查语音设置
                voice_app_id = st.session_state.api_keys.get('voice_app_id')
                voice_token = st.session_state.api_keys.get('voice_token')
                print(f"[DEBUG][select_character] 开始交互前检查语音设置: enabled={st.session_state.voice_enabled}, app_id={voice_app_id[:5] if voice_app_id else None}***, token={'YES' if voice_token else 'NO'}")
                logger.info(f"[DEBUG][select_character] 开始交互前检查语音设置: enabled={st.session_state.voice_enabled}, app_id={voice_app_id[:5] if voice_app_id else None}***, token={'YES' if voice_token else 'NO'}")
                
                # 启动交互
                start_context = {
                    'action': 'start',
                    'document_id': st.session_state.document_id,
                    'character_name': name,
                    'chapter': st.session_state.current_chapter,
                    'knowledge_base': st.session_state.knowledge_base,
                    'access_key_id': access_key_id,
                    'secret_key': secret_key,
                    'auto_image': True,
                    'auto_voice': st.session_state.voice_enabled,
                    'voice_app_id': voice_app_id,
                    'voice_token': voice_token
                }
                
                with st.spinner(f"正在初始化 {name} 的故事..."):
                    result = st.session_state.coordinator.execute_agent('interaction', start_context)
                    
                    if result.get('status') == 'success':
                        st.session_state.current_scene = result.get('scene')
                        
                        # 如果自动生成了图像，保存URL
                        if 'image_url' in result:
                            st.session_state.image_url = result['image_url']
                            st.session_state.remote_url = None
                        elif 'remote_url' in result:
                            st.session_state.remote_url = result['remote_url']
                            st.session_state.image_url = None
                            
                        # 如果自动生成了语音，保存对话
                        if 'audio_result' in result and result['audio_result'].get('status') == 'success':
                            st.session_state.current_dialogues = result['audio_result'].get('dialogues', [])
                            st.session_state.last_scene_id = result.get('scene', {}).get('interaction_id', '')
                            
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
            print("[DEBUG][app.py 下一章] auto_voice:", st.session_state.voice_enabled)
            with st.spinner("正在进入下一章..."):
                # 获取API密钥
                access_key_id = st.session_state.api_keys.get('image_access_key_id')
                secret_key = st.session_state.api_keys.get('image_secret_key')
                
                # 获取语音API配置
                voice_app_id = st.session_state.api_keys.get('voice_app_id')
                voice_token = st.session_state.api_keys.get('voice_token')
                
                result = st.session_state.coordinator.execute_agent('interaction', {
                    'action': 'next_chapter',
                    'access_key_id': access_key_id,
                    'secret_key': secret_key,
                    'auto_image': True,
                    'auto_voice': st.session_state.voice_enabled,
                    'voice_app_id': voice_app_id,
                    'voice_token': voice_token
                })
                if result.get('status') == 'success':
                    # 更新当前章节编号
                    st.session_state.current_chapter += 1
                    st.session_state.current_scene = result.get('scene')
                    
                    # 如果自动生成了图像，保存URL
                    if 'image_url' in result:
                        st.session_state.image_url = result['image_url']
                        st.session_state.remote_url = None
                    elif 'remote_url' in result:
                        st.session_state.remote_url = result['remote_url']
                        st.session_state.image_url = None
                        
                    # 如果自动生成了语音，保存对话
                    if 'audio_result' in result and result['audio_result'].get('status') == 'success':
                        st.session_state.current_dialogues = result['audio_result'].get('dialogues', [])
                        st.session_state.last_scene_id = result.get('scene', {}).get('interaction_id', '')
                        
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
            print("[DEBUG][app.py 跳转章节] auto_voice:", st.session_state.voice_enabled)
            with st.spinner(f"正在跳转到第{target_chapter}章..."):
                # 获取API密钥
                access_key_id = st.session_state.api_keys.get('image_access_key_id')
                secret_key = st.session_state.api_keys.get('image_secret_key')
                
                # 获取语音API配置
                voice_app_id = st.session_state.api_keys.get('voice_app_id')
                voice_token = st.session_state.api_keys.get('voice_token')
                
                result = st.session_state.coordinator.execute_agent('interaction', {
                    'action': 'jump_to',
                    'chapter': target_chapter,
                    'access_key_id': access_key_id,
                    'secret_key': secret_key,
                    'auto_image': True,
                    'auto_voice': st.session_state.voice_enabled,
                    'voice_app_id': voice_app_id,
                    'voice_token': voice_token
                })
                if result.get('status') == 'success':
                    st.session_state.current_chapter = target_chapter
                    st.session_state.current_scene = result.get('scene')
                    
                    # 如果自动生成了图像，保存URL
                    if 'image_url' in result:
                        st.session_state.image_url = result['image_url']
                        st.session_state.remote_url = None
                    elif 'remote_url' in result:
                        st.session_state.remote_url = result['remote_url']
                        st.session_state.image_url = None
                        
                    # 如果自动生成了语音，保存对话
                    if 'audio_result' in result and result['audio_result'].get('status') == 'success':
                        st.session_state.current_dialogues = result['audio_result'].get('dialogues', [])
                        st.session_state.last_scene_id = result.get('scene', {}).get('interaction_id', '')
                        
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
        # 检查是否是偏离结局
        is_deviated_ending = scene.get('deviated_ending', False)
        
        if is_deviated_ending:
            st.warning("⚠️ 偏离主线结局")
            ending_type = scene.get('ending_type', '未知')
            st.markdown(f"### 偏离结局类型: {ending_type}")
            
            if 'deviation_summary' in scene:
                st.markdown(f"**关键偏离点**: {scene.get('deviation_summary')}")
                
            # 在偏离结局后添加额外选项
            st.markdown("---")
            st.markdown("### 偏离结局后的选择")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("重新开始", key="restart_after_deviation"):
                    # 停止交互
                    st.session_state.coordinator.execute_agent('interaction', {'action': 'stop'})
                    # 清除状态
                    st.session_state.character_name = None
                    st.session_state.current_scene = None
                    if 'search_results' in st.session_state:
                        del st.session_state.search_results
                    st.rerun()
                    
            with col2:
                if st.button("返回上一章", key="return_to_prev_chapter"):
                    # 如果当前不是第一章，则返回上一章
                    if st.session_state.current_chapter > 1:
                        with st.spinner(f"正在返回第{st.session_state.current_chapter-1}章..."):
                            result = st.session_state.coordinator.execute_agent('interaction', {
                                'action': 'jump_to',
                                'chapter': st.session_state.current_chapter - 1
                            })
                            if result.get('status') == 'success':
                                st.session_state.current_chapter -= 1
                                st.session_state.current_scene = result.get('scene')
                                st.rerun()
                    else:
                        st.error("当前已是第一章，无法返回上一章")
            
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
        
        # 添加语音播放功能
        if st.session_state.voice_enabled and st.session_state.api_keys.get('voice_app_id'):
            # 音量控制
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown("### 音量控制")
            with col2:
                if "audio_volume" not in st.session_state:
                    st.session_state.audio_volume = 100
                volume = st.slider("音量", 0, 100, st.session_state.audio_volume, 5, key="volume_slider")
                st.session_state.audio_volume = volume
                
            # 批量播放所有对话
            if hasattr(st.session_state, 'current_dialogues') and len([d for d in st.session_state.current_dialogues if 'audio_path' in d]) > 0:
                if st.button("播放所有对话", key="play_all_dialogues"):
                    # 获取所有音频对话的路径
                    audio_paths = [d['audio_path'] for d in st.session_state.current_dialogues if 'audio_path' in d]
                    # 创建JavaScript代码自动依次播放所有音频
                    audio_js_code = """
                    <script>
                    // 存储所有音频元素的ID
                    var audioIds = [];
                    // 当前正在播放的音频索引
                    var currentAudioIndex = 0;
                    
                    // 初始化函数
                    function initializeAudioSequence() {
                        // 查找所有音频元素并存储它们的ID
                        document.querySelectorAll('audio').forEach(function(audio) {
                            audioIds.push(audio.id);
                            // 设置音量
                            audio.volume = """ + str(st.session_state.audio_volume / 100) + """;
                        });
                        
                        // 为每个音频元素添加结束事件监听器
                        audioIds.forEach(function(id, index) {
                            var audio = document.getElementById(id);
                            audio.addEventListener('ended', function() {
                                // 播放下一个音频
                                playNextAudio(index);
                            });
                        });
                        
                        // 开始播放第一个音频
                        if (audioIds.length > 0) {
                            var firstAudio = document.getElementById(audioIds[0]);
                            currentAudioIndex = 0;
                            firstAudio.play();
                        }
                    }
                    
                    // 播放下一个音频
                    function playNextAudio(currentIndex) {
                        // 确保索引是有效的
                        if (currentIndex >= audioIds.length - 1) {
                            // 已到达最后一个音频，停止播放
                            return;
                        }
                        
                        // 获取下一个音频元素
                        var nextIndex = currentIndex + 1;
                        var nextAudio = document.getElementById(audioIds[nextIndex]);
                        currentAudioIndex = nextIndex;
                        
                        // 播放下一个音频
                        if (nextAudio) {
                            nextAudio.play();
                        }
                    }
                    
                    // 页面加载完成后执行初始化
                    document.addEventListener('DOMContentLoaded', initializeAudioSequence);
                    </script>
                    """
                    st.markdown(audio_js_code, unsafe_allow_html=True)
                    st.info("开始播放所有对话")
            
            # 显示对话内容与对应的语音（集成在场景描述中）
            if hasattr(st.session_state, 'current_dialogues') and st.session_state.current_dialogues:
                # 创建对话字典，以说话者和内容为键
                dialogues_dict = {}
                for dialogue in st.session_state.current_dialogues:
                    if 'audio_path' in dialogue:
                        key = (dialogue.get('speaker', ''), dialogue.get('content', ''))
                        dialogues_dict[key] = dialogue['audio_path']
                
                # 分割场景文本并添加音频播放器
                lines = narrative.split('\n')
                formatted_narrative = ""
                
                for line in lines:
                    formatted_narrative += line + "\n"
                    
                    # 检查这行是否是对话
                    if ('：' in line or ': ' in line) and len(line.split('：' if '：' in line else ': ', 1)) > 1:
                        speaker, content = line.split('：' if '：' in line else ': ', 1)
                        speaker = speaker.strip()
                        content = content.strip()
                        
                        # 检查是否有对应的音频
                        if (speaker, content) in dialogues_dict:
                            audio_path = dialogues_dict[(speaker, content)]
                            # 添加音频播放控件的HTML，添加音量控制
                            formatted_narrative += f"""
<div style="margin-left: 20px; margin-bottom: 10px;">
<audio id="audio_{hash((speaker, content))}" controls style="width: 250px;">
  <source src="{audio_path}" type="audio/mp3">
  你的浏览器不支持音频元素。
</audio>
<script>
  document.getElementById('audio_{hash((speaker, content))}').volume = {st.session_state.audio_volume / 100};
</script>
</div>
"""
                
                # 使用markdown显示带有音频播放器的场景描述
                st.markdown(formatted_narrative, unsafe_allow_html=True)
            else:
                # 如果没有对话语音，直接显示场景文本
                st.markdown(f"{narrative}")
                
            # 自动播放设置的JavaScript代码
            if st.session_state.audio_autoplay and hasattr(st.session_state, 'current_dialogues') and st.session_state.current_dialogues:
                # 找到第一个有音频的对话
                first_audio = next((d['audio_path'] for d in st.session_state.current_dialogues if 'audio_path' in d), None)
                if first_audio:
                    st.markdown(f"""
                    <script>
                        document.addEventListener('DOMContentLoaded', function() {{
                            const audioElements = document.querySelectorAll('audio');
                            if (audioElements.length > 0) {{
                                audioElements[0].volume = {st.session_state.audio_volume / 100};
                                audioElements[0].play();
                            }}
                        }});
                    </script>
                    """, unsafe_allow_html=True)
        else:
            # 如果没有启用语音功能，直接显示场景描述
            st.markdown(f"{narrative}")
        
        # 显示交互点
        st.markdown(f"## 互动")
        st.markdown(f"_{scene.get('interaction_point', '')}_")
        
        if 'context_hint' in scene and scene['context_hint']:
            with st.expander("提示"):
                st.markdown(f"{scene.get('context_hint', '')}")
        
        # 用户输入
        if 'user_input_area' not in st.session_state:
            st.session_state.user_input_area = ""
            
        user_input = st.text_area("你的选择", 
                                  value=st.session_state.user_input_area, 
                                  height=100, 
                                  key="user_input_area")
        
        # 提交选择
        if st.button("确认", type="primary") and user_input:
            print("[DEBUG][app.py 确认按钮] auto_voice:", st.session_state.voice_enabled)
            with st.spinner("思考中..."):
                # 获取API密钥
                access_key_id = st.session_state.api_keys.get('image_access_key_id')
                secret_key = st.session_state.api_keys.get('image_secret_key')
                
                # 获取语音API配置
                voice_app_id = st.session_state.api_keys.get('voice_app_id')
                voice_token = st.session_state.api_keys.get('voice_token')
                
                # 处理用户选择
                result = st.session_state.coordinator.execute_agent('interaction', {
                    'action': 'continue',
                    'user_input': user_input,
                    'access_key_id': access_key_id,
                    'secret_key': secret_key,
                    'auto_image': True,
                    'auto_voice': st.session_state.voice_enabled,
                    'voice_app_id': voice_app_id,
                    'voice_token': voice_token
                })
                
                # 如果检测到偏离
                if result.get('status') == 'warning':
                    divergence = result.get('divergence', {})
                    st.warning(f"检测到故事偏离: {divergence.get('description')}")
                    st.warning(f"偏离等级: {divergence.get('level')}/5")
                    
                    # 仅当偏离等级高于4时才显示确认选项
                    if divergence.get('level', 0) >= 4:
                        # 高偏离度，显示确认选项
                        st.error("这个选择将导致故事严重偏离原定情节，确定要继续吗？")
                        col1, col2 = st.columns(2)
                        
                        # 临时保存当前的用户输入，以便后续使用
                        if 'last_divergent_input' not in st.session_state:
                            st.session_state.last_divergent_input = user_input
                        
                        with col1:
                            if st.button("是，继续偏离", key="continue_divergence"):
                                with st.spinner("生成偏离结局..."):
                                    # 使用force_continue参数请求偏离结局
                                    deviation_result = st.session_state.coordinator.execute_agent('interaction', {
                                        'action': 'continue',
                                        'user_input': st.session_state.last_divergent_input,
                                        'force_continue': True,  # 明确设置为True
                                        'access_key_id': access_key_id,
                                        'secret_key': secret_key,
                                        'auto_image': True,
                                        'auto_voice': st.session_state.voice_enabled,
                                        'voice_app_id': voice_app_id,
                                        'voice_token': voice_token
                                    })
                                    
                                    if deviation_result.get('status') == 'deviated_ending' or deviation_result.get('status') == 'success':
                                        # 直接更新场景并显示
                                        st.session_state.current_scene = deviation_result.get('scene')
                                        
                                        # 如果自动生成了图像，保存URL
                                        if 'image_url' in deviation_result:
                                            st.session_state.image_url = deviation_result['image_url']
                                            st.session_state.remote_url = None
                                        elif 'remote_url' in deviation_result:
                                            st.session_state.remote_url = deviation_result['remote_url']
                                            st.session_state.image_url = None
                                        
                                        # 清除输入框内容，防止重复提交
                                        st.session_state.user_input_area = ""
                                        # 删除临时保存的输入内容
                                        if 'last_divergent_input' in st.session_state:
                                            del st.session_state.last_divergent_input
                                        
                                        try:
                                            if deviation_result.get('status') == 'deviated_ending':
                                                st.success("已生成偏离主线的结局")
                                            else:
                                                st.success("已继续故事发展")
                                        except Exception as e:
                                            st.error(f"UI更新失败，但场景已更新: {str(e)}")
                                            
                                        st.rerun()
                                    else:
                                        st.error(f"生成偏离结局失败: {deviation_result.get('message')}")
                                        
                        with col2:
                            if st.button("否，重新选择", key="reject_divergence"):
                                # 清除输入框内容，让用户重新输入
                                st.session_state.user_input_area = ""
                                # 删除临时保存的输入内容
                                if 'last_divergent_input' in st.session_state:
                                    del st.session_state.last_divergent_input
                                st.info("请重新输入您的选择")
                                st.rerun()
                
                elif result.get('status') == 'success':
                    st.session_state.current_scene = result.get('scene')
                    
                    # 如果自动生成了图像，保存URL
                    if 'image_url' in result:
                        st.session_state.image_url = result['image_url']
                        st.session_state.remote_url = None
                    elif 'remote_url' in result:
                        st.session_state.remote_url = result['remote_url']
                        st.session_state.image_url = None
                    
                    # 如果自动生成了语音，保存对话
                    if 'audio_result' in result and result['audio_result'].get('status') == 'success':
                        st.session_state.current_dialogues = result['audio_result'].get('dialogues', [])
                        st.session_state.last_scene_id = result.get('scene', {}).get('interaction_id', '')
                    
                    # 检查是否应该进入下一章
                    if result.get('should_proceed_chapter'):
                        st.info("已达到章节结尾，可以进入下一章")
                    
                    st.rerun()
                
                # 处理偏离结局响应
                elif result.get('status') == 'deviated_ending':
                    st.session_state.current_scene = result.get('scene')
                    
                    # 如果自动生成了图像，保存URL
                    if 'image_url' in result:
                        st.session_state.image_url = result['image_url']
                        st.session_state.remote_url = None
                    elif 'remote_url' in result:
                        st.session_state.remote_url = result['remote_url']
                        st.session_state.image_url = None
                    
                    # 显示这是一个偏离结局的提示
                    st.info("这是一个偏离主线的结局。您可以选择回到之前的章节，或开始新的故事。")
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