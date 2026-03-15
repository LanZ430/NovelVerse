"""图像生成器模块，负责根据场景生成图像

该模块提供基于场景描述生成相应图像的功能，支持多种艺术风格。
"""

from typing import Dict, Any, Optional
import logging
import time
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class ImageGenerator:
    """图像生成器，负责基于场景生成图像"""
    
    def __init__(self, client, llm_model, document_language='chinese', image_service=None):
        """初始化图像生成器
        
        Args:
            client: LLM客户端
            llm_model: 使用的语言模型
            document_language: 文档语言，默认'chinese'
            image_service: 图像服务模块
        """
        self.client = client
        self.llm_model = llm_model
        self.document_language = document_language
        self.image_service = image_service
    
    def generate_image_from_scene(self, scene: Dict[str, Any], 
                                 access_key_id: str = None, 
                                 secret_key: str = None, 
                                 base_url: str = None, 
                                 style: str = "realistic", 
                                 size: str = "512x512") -> Dict[str, Any]:
        """基于场景生成图像
        
        Args:
            scene: 场景信息
            access_key_id: 图像API的Access Key ID
            secret_key: 图像API的Secret Key
            base_url: 图像API的Base URL
            style: 图像风格，支持：realistic, anime, painting, sketch, 3d
            size: 图像尺寸，例如 "512x512"
            
        Returns:
            Dict[str, Any]: 图像信息
        """
        try:
            # 如果image_service未设置，尝试导入
            if self.image_service is None:
                try:
                    from agent.services.image_service import ImageService
                    self.image_service = ImageService(access_key_id, secret_key, base_url)
                except ImportError:
                    logger.error("无法导入ImageService")
                    return {
                        "status": "error",
                        "message": "图像服务模块未找到"
                    }
            
            # 提取场景描述
            narrative = scene.get('narrative', '')
            key_elements = scene.get('key_elements', [])
            emotion_state = scene.get('emotion_state', {})
            
            # 构建更丰富的场景描述
            # 1. 从叙述中提取主要内容
            scene_description = narrative[:300]  # 截取前300个字符作为主要描述
            
            # 2. 添加关键元素
            if key_elements:
                elements_text = "，".join(key_elements[:3])
                scene_description += f"。场景中包含：{elements_text}"
            
            # 3. 添加情感状态描述，让图像更有情感表现
            if isinstance(emotion_state, dict) and emotion_state:
                emotions = []
                for character, emotion in emotion_state.items():
                    emotions.append(f"{character}：{emotion}")
                if emotions:
                    scene_description += f"。情感氛围：{'，'.join(emotions[:2])}"
            elif isinstance(emotion_state, str):
                scene_description += f"。情感氛围：{emotion_state}"
            
            # 生成图像
            result = self.image_service.generate_image(
                prompt=scene_description,
                style=style,
                size=size
            )
            
            # 返回结果
            return {
                "status": "success",
                "image_url": result.get('image_url'),
                "remote_url": result.get('remote_url', ''),
                "prompt": result.get('prompt', scene_description),
                "style": style
            }
        except Exception as e:
            logger.exception(f"生成图像失败: {str(e)}")
            return {
                "status": "error",
                "message": f"生成图像失败: {str(e)}"
            }
    
    def determine_image_style(self, scene: Dict[str, Any]) -> str:
        """使用LLM分析场景，确定最适合的图像风格
        
        Args:
            scene: 场景信息
            
        Returns:
            str: 推荐的图像风格，可能为："realistic", "anime", "painting", "sketch", "3d"
        """
        try:
            # 提取场景描述和关键元素
            narrative = scene.get('narrative', '')
            key_elements = scene.get('key_elements', [])
            emotion_state = scene.get('emotion_state', {})
            
            # 提取情感状态文本
            emotion_text = ""
            if isinstance(emotion_state, dict):
                emotion_text = ", ".join([f"{k}: {v}" for k, v in emotion_state.items()])
            else:
                emotion_text = str(emotion_state)
            
            # 构建提示
            prompt = f"""你是一位专业的视觉艺术指导，需要为以下场景选择最合适的视觉风格。请基于场景描述、人物情感和关键元素，选择最适合的图像风格。

### 场景描述
{narrative[:300]}

### 情感状态
{emotion_text}

### 关键元素
{', '.join(key_elements) if key_elements else "无"}

请分析这个场景的氛围、情绪、和内容，然后从以下选项中选择一种最适合的图像风格：
1. realistic - 写实风格，适合真实场景、人物肖像、自然风景等
2. anime - 动漫风格，适合可爱、轻松、活泼的场景或角色
3. painting - 绘画风格，适合梦幻、艺术、抽象或富有想象力的场景
4. sketch - 素描风格，适合紧张、黑暗、情感强烈或戏剧性场景
5. 3d - 3D渲染风格，适合未来场景、科技元素、或需要特殊视觉效果的场景

只回答一个单词作为风格选择："realistic", "anime", "painting", "sketch", 或 "3d"。"""

            # 调用LLM确定风格
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.1,
                max_tokens=20
            )
            
            content = response.choices[0].message.content.strip().lower()
            
            # 提取风格关键词
            valid_styles = ["realistic", "anime", "painting", "sketch", "3d"]
            
            # 如果结果直接匹配有效风格，则返回
            for style in valid_styles:
                if style in content:
                    logger.info(f"LLM推荐的图像风格: {style}")
                    return style
            
            # 如果没有明确匹配，尝试查找替代词
            style_map = {
                "写实": "realistic", "逼真": "realistic", "真实": "realistic", "photorealistic": "realistic", "real": "realistic",
                "动漫": "anime", "卡通": "anime", "cartoon": "anime", "萌": "anime", "可爱": "anime", "cute": "anime",
                "绘画": "painting", "艺术": "painting", "水彩": "painting", "油画": "painting", "art": "painting", "dream": "painting",
                "素描": "sketch", "铅笔": "sketch", "黑白": "sketch", "线条": "sketch", "速写": "sketch", "pencil": "sketch",
                "3d": "3d", "三维": "3d", "渲染": "3d", "立体": "3d", "科技": "3d", "未来": "3d", "render": "3d"
            }
            
            for term, style in style_map.items():
                if term in content:
                    logger.info(f"LLM提及相关词'{term}'，选择图像风格: {style}")
                    return style
            
            # 默认返回写实风格
            logger.info("无法确定明确风格，默认使用写实风格")
            return "realistic"
            
        except Exception as e:
            logger.error(f"确定图像风格时出错: {str(e)}")
            return "realistic"  # 出错时默认使用写实风格
    
    def auto_generate_image(self, scene: Dict[str, Any], 
                          access_key_id: str, 
                          secret_key: str, 
                          base_url: str = None) -> Dict[str, Any]:
        """自动为场景生成图像
        
        Args:
            scene: 场景信息
            access_key_id: API访问密钥ID
            secret_key: API密钥
            base_url: API基础URL
            
        Returns:
            Dict[str, Any]: 图像生成结果
        """
        if not access_key_id or not secret_key:
            logger.warning("未设置图像生成API密钥，无法自动生成图像")
            return {
                "status": "error",
                "message": "未设置图像生成API密钥"
            }
            
        # 判断场景是否适合生成图像
        if not self._evaluate_scene_for_image(scene):
            logger.info("当前场景不适合生成图像，跳过自动生成")
            return {
                "status": "skipped",
                "message": "当前场景不适合生成图像"
            }
            
        # 适合生成图像，调用图像生成方法
        logger.info("当前场景适合生成图像，开始自动生成...")
        try:
            # 使用LLM确定最适合的图像风格
            style = self.determine_image_style(scene)
            logger.info(f"为场景选择的图像风格: {style}")
            
            # 生成图像
            return self.generate_image_from_scene(
                scene,
                access_key_id=access_key_id,
                secret_key=secret_key,
                base_url=base_url,
                style=style,
                size="512x512"
            )
        except Exception as e:
            logger.exception(f"自动生成图像失败: {str(e)}")
            return {
                "status": "error",
                "message": f"自动生成图像失败: {str(e)}"
            }
    
    def _evaluate_scene_for_image(self, scene: Dict[str, Any]) -> bool:
        """评估场景是否适合生成图像
        
        Args:
            scene: 场景信息
            
        Returns:
            bool: 是否适合生成图像
        """
        # 这里可以添加更复杂的评估逻辑，目前简单地检查是否有文本内容
        if not scene or not scene.get('narrative'):
            return False
            
        # 检查文本长度是否足够
        if len(scene.get('narrative', '')) < 50:
            return False
            
        # 判断是否有有效的场景元素
        if not scene.get('key_elements'):
            return False
            
        return True 