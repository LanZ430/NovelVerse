import streamlit as st
from pathlib import Path
import asyncio
from typing import Optional

from app.core.document import NovelProcessor
from app.core.agent import StoryAgent
from app.api.image import ImageGenerator
from app.api.video import VideoGenerator
from config.config import settings

# 页面配置
st.set_page_config(
    page_title="沉浸式小说体验",
    page_icon="📚",
    layout="wide"
)

# 初始化会话状态
if "novel_id" not in st.session_state:
    st.session_state.novel_id = None
if "agent" not in st.session_state:
    st.session_state.agent = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def process_novel_upload(uploaded_file) -> Optional[str]:
    """处理上传的小说文件"""
    if uploaded_file is None:
        return None
        
    # 保存上传的文件
    novel_path = settings.NOVEL_DIR / uploaded_file.name
    novel_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(novel_path, "wb") as f:
        f.write(uploaded_file.getvalue())
        
    try:
        # 处理小说文件
        processor = NovelProcessor(novel_path)
        processor.process_novel()
        return novel_path.stem
    except Exception as e:
        st.error(f"处理文件时出错: {str(e)}")
        if novel_path.exists():
            novel_path.unlink()  # 删除上传的文件
        return None

def main():
    st.title("📚 沉浸式小说世界体验")
    
    # 侧边栏：文件上传和角色选择
    with st.sidebar:
        st.header("设置")
        uploaded_file = st.file_uploader(
            "上传小说文件",
            type=["txt", "pdf", "doc", "docx"],
            help="支持txt、pdf、doc、docx格式的文件"
        )
        
        if uploaded_file:
            with st.spinner("正在处理文件..."):
                novel_id = process_novel_upload(uploaded_file)
                if novel_id:
                    st.session_state.novel_id = novel_id
                    st.success("文件处理完成！")
        
        role = st.selectbox(
            "选择视角",
            ["observer", "protagonist", "supporting"],
            format_func=lambda x: {
                "observer": "观察者",
                "protagonist": "主角",
                "supporting": "配角"
            }[x]
        )
        
        if st.session_state.novel_id and (
            not st.session_state.agent or 
            st.session_state.agent.role != role
        ):
            st.session_state.agent = StoryAgent(
                novel_id=st.session_state.novel_id,
                role=role
            )
    
    # 主界面
    if st.session_state.novel_id is None:
        st.info("👈 请先上传小说文件")
        return
        
    # 聊天界面
    st.header("与故事世界对话")
    
    # 显示聊天历史
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if "image" in message:
                st.image(message["image"])
            if "video" in message:
                st.video(message["video"])
    
    # 用户输入
    if prompt := st.chat_input("输入你想说的话..."):
        # 添加用户消息
        st.session_state.chat_history.append({
            "role": "user",
            "content": prompt
        })
        
        with st.chat_message("user"):
            st.write(prompt)
        
        # 生成回应
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                # 获取AI回应
                response = asyncio.run(
                    st.session_state.agent.generate_response(prompt)
                )
                
                # 创建回应消息
                message = {
                    "role": "assistant",
                    "content": response
                }
                
                # 检查是否需要生成图像或视频
                if "描绘" in prompt or "画面" in prompt:
                    image_gen = ImageGenerator()
                    image = image_gen.generate_image(prompt)
                    if image:
                        message["image"] = image
                        
                if "动作" in prompt or "场景" in prompt:
                    video_gen = VideoGenerator()
                    video_url = video_gen.generate_video(prompt)
                    if video_url:
                        message["video"] = video_url
                
                # 添加到聊天历史
                st.session_state.chat_history.append(message)
                
                # 显示回应
                st.write(response)
                if "image" in message:
                    st.image(message["image"])
                if "video" in message:
                    st.video(message["video"])

if __name__ == "__main__":
    main() 