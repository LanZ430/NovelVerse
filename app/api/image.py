import requests
from pathlib import Path
from typing import Optional, Dict
from PIL import Image
import io
import base64
from config.config import settings

class ImageGenerator:
    def __init__(self):
        self.api_key = settings.VOLCENGINE_API_KEY
        self.api_secret = settings.VOLCENGINE_API_SECRET
        self.base_url = "https://api.volcengine.com/v1/vision/image-generation"
        
    def _prepare_headers(self) -> Dict:
        """准备API请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    def generate_image(self, 
                      prompt: str,
                      negative_prompt: str = "",
                      size: tuple = settings.IMAGE_SIZE,
                      output_path: Optional[Path] = None) -> Optional[Image.Image]:
        """生成图像"""
        headers = self._prepare_headers()
        
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": size[0],
            "height": size[1],
            "steps": 50,
            "n": 1
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            if "image" in result:
                image_data = base64.b64decode(result["image"])
                image = Image.open(io.BytesIO(image_data))
                
                # 如果指定了输出路径，保存图像
                if output_path:
                    image.save(output_path)
                
                return image
            
        except requests.exceptions.RequestException as e:
            print(f"Error generating image: {e}")
            return None
        
    def enhance_image(self,
                     image: Image.Image,
                     prompt: str,
                     strength: float = 0.5) -> Optional[Image.Image]:
        """增强现有图像"""
        # TODO: 实现图像增强逻辑
        pass 