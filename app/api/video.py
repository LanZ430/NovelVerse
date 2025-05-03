import requests
from pathlib import Path
from typing import Optional, Dict
import json
from config.config import settings

class VideoGenerator:
    def __init__(self):
        self.api_key = settings.VOLCENGINE_API_KEY
        self.api_secret = settings.VOLCENGINE_API_SECRET
        self.base_url = "https://api.volcengine.com/v1/vision/video-generation"
        
    def _prepare_headers(self) -> Dict:
        """准备API请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    def generate_video(self,
                      prompt: str,
                      duration: int = settings.VIDEO_LENGTH,
                      output_path: Optional[Path] = None) -> Optional[str]:
        """生成视频"""
        headers = self._prepare_headers()
        
        payload = {
            "prompt": prompt,
            "duration": duration,
            "fps": 24,
            "quality": "high"
        }
        
        try:
            # 发起生成请求
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            # 获取任务ID
            result = response.json()
            task_id = result.get("task_id")
            
            if task_id:
                # 轮询获取生成结果
                video_url = self._poll_result(task_id)
                
                if video_url and output_path:
                    # 下载视频
                    self._download_video(video_url, output_path)
                
                return video_url
            
        except requests.exceptions.RequestException as e:
            print(f"Error generating video: {e}")
            return None
            
    def _poll_result(self, task_id: str, max_attempts: int = 30) -> Optional[str]:
        """轮询获取生成结果"""
        headers = self._prepare_headers()
        poll_url = f"{self.base_url}/tasks/{task_id}"
        
        for _ in range(max_attempts):
            try:
                response = requests.get(poll_url, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                status = result.get("status")
                
                if status == "completed":
                    return result.get("video_url")
                elif status == "failed":
                    print(f"Video generation failed: {result.get('error')}")
                    return None
                    
                # 等待5秒后重试
                import time
                time.sleep(5)
                
            except requests.exceptions.RequestException as e:
                print(f"Error polling result: {e}")
                return None
                
        print("Max polling attempts reached")
        return None
        
    def _download_video(self, url: str, output_path: Path) -> bool:
        """下载视频到指定路径"""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error downloading video: {e}")
            return False 