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