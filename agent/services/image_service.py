from typing import Dict, Any, Optional
import logging
import requests
import base64
import json
import os
import hmac
import hashlib
import datetime
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)

class ImageService:
    """图像生成服务，负责文本到图像的生成，使用即梦API"""
    
    def __init__(self, access_key_id: str, secret_access_key: str, base_url: Optional[str] = None):
        """初始化图像生成服务
        
        Args:
            access_key_id: 访问密钥ID
            secret_access_key: 访问密钥
            base_url: API基础URL（可选，默认为火山引擎视觉API地址）
        """
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.base_url = base_url or "https://visual.volcengineapi.com"
        self.service = "cv"
        self.region = "cn-north-1"
        self.image_dir = Path("./data/images")
        self.image_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_headers(self, action: str, version: str, payload: Dict[str, Any]) -> Dict[str, str]:
        """生成请求头，包括签名
        
        Args:
            action: API动作
            version: API版本
            payload: 请求体数据
            
        Returns:
            Dict[str, str]: 请求头
        """
        # 时间戳
        now = datetime.datetime.utcnow()
        date_stamp = now.strftime('%Y%m%d')
        time_stamp = now.strftime('%Y%m%dT%H%M%SZ')
        
        # 准备签名所需数据
        canonical_headers = f"content-type:application/json\nhost:visual.volcengineapi.com\nx-date:{time_stamp}\n"
        signed_headers = "content-type;host;x-date"
        
        # 规范请求
        canonical_request = f"POST\n/\n"
        canonical_request += f"Action={action}&Version={version}\n"
        canonical_request += canonical_headers + "\n"
        canonical_request += signed_headers + "\n"
        
        # 请求体的哈希值
        payload_json = json.dumps(payload)
        payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
        canonical_request += payload_hash
        
        # 计算签名
        algorithm = 'HMAC-SHA256'
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/request"
        
        string_to_sign = f"{algorithm}\n{time_stamp}\n{credential_scope}\n"
        string_to_sign += hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        
        # 计算签名密钥
        k_date = hmac.new(self.secret_access_key.encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
        k_region = hmac.new(k_date, self.region.encode('utf-8'), hashlib.sha256).digest()
        k_service = hmac.new(k_region, self.service.encode('utf-8'), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"request", hashlib.sha256).digest()
        
        # 计算签名
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # 构建授权头
        credential = f"{self.access_key_id}/{credential_scope}"
        auth_header = f"{algorithm} Credential={credential}, SignedHeaders={signed_headers}, Signature={signature}"
        
        # 返回请求头
        return {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Date": time_stamp,
            "X-Amz-Date": time_stamp,
            "Host": "visual.volcengineapi.com"
        }
    
    def _sanitize_prompt(self, prompt: str) -> str:
        """处理提示词以避免内容审核问题
        
        Args:
            prompt: 原始提示词
            
        Returns:
            str: 处理后的安全提示词
        """
        # 敏感话题或词汇的替换
        replacements = {
            "裸体": "人物",
            "性": "关系",
            "血腥": "红色",
            "暴力": "行动",
            "色情": "艺术",
            "政治": "讨论",
            "宗教": "信仰",
            "恐怖": "紧张",
            "自杀": "伤心",
            "毒品": "物品",
            "枪": "工具",
            "武器": "装备",
            # 可根据需要添加更多替换规则
        }
        
        sanitized = prompt
        for word, replacement in replacements.items():
            sanitized = sanitized.replace(word, replacement)
            
        # 添加安全限定词
        safe_prefixes = ["安全的", "和谐的", "健康的"]
        if not any(prefix in sanitized for prefix in safe_prefixes):
            sanitized = f"{safe_prefixes[0]} {sanitized}"
            
        return sanitized
    
    def generate_image(self, prompt: str, negative_prompt: str = "", style: str = "realistic", size: str = "512x512") -> Dict[str, Any]:
        """生成图像
        
        Args:
            prompt: 图像生成提示（场景描述）
            negative_prompt: 负面提示（不希望在图像中出现的内容，暂不使用）
            style: 图像风格，支持：realistic, anime, painting, sketch, 3d
            size: 图像尺寸，支持：512x512, 512x384, 384x512, 等比例尺寸
            
        Returns:
            Dict[str, Any]: 生成结果，包括：
                - status: 生成状态
                - image_url: 图像URL（本地路径或远程URL）
                - prompt: 最终使用的提示词（可能被API优化过）
                - error: 错误信息（如果有）
        """
        try:
            # 解析尺寸
            width, height = map(int, size.split('x'))
            
            # 确保尺寸在有效范围内
            width = max(256, min(768, width))
            height = max(256, min(768, height))
            
            # 根据风格选择适合的描述前缀
            style_prefix = self._get_style_prefix(style)
            
            # 格式化提示词，符合即梦API建议的【艺术风格】+【主体描述】+【文字排版】格式
            if not any(p in prompt for p in ["写实风格", "动漫风格", "绘画风格", "素描风格", "3D渲染"]):
                styled_prompt = f"{style_prefix}，{prompt}"
            else:
                styled_prompt = prompt
                
            # 处理提示词，确保内容安全
            sanitized_prompt = self._sanitize_prompt(styled_prompt)
            
            # 构建请求数据
            payload = {
                "req_key": "jimeng_high_aes_general_v21_L",  # 使用即梦API的服务标识
                "prompt": sanitized_prompt,
                "seed": -1,
                "width": width,
                "height": height,
                "use_pre_llm": True,  # 启用API的提示词优化
                "use_sr": True,
                "return_url": True
            }
            
            # 确定API动作和版本
            action = "CVProcess"
            version = "2022-08-31"
            
            # 获取带有签名的请求头
            headers = self._generate_headers(action, version, payload)
                
            # 构建URL
            url = f"{self.base_url}?Action={action}&Version={version}"
                
            # 发送请求
            response = requests.post(
                url,
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"图像生成失败: {response.status_code}")
                logger.error(f"错误信息: {response.text}")
                return {
                    "status": "error",
                    "error": f"图像生成API返回错误: {response.status_code} - {response.text}",
                    "original_prompt": styled_prompt,
                    "sanitized_prompt": sanitized_prompt
                }
                
            # 处理响应
            response_data = response.json()
            
            # 检查响应状态
            if response_data.get("code") != 10000:
                logger.error(f"图像生成请求失败: {response_data.get('message')}")
                return {
                    "status": "error",
                    "error": f"图像生成请求失败: {response_data.get('message')}",
                    "original_prompt": styled_prompt,
                    "sanitized_prompt": sanitized_prompt
                }
            
            # 获取图像数据
            data = response_data.get("data", {})
            image_urls = data.get("image_urls", [])
            
            # 获取API优化后的提示词 - 即梦API有几种可能的优化结果字段
            optimized_prompt = data.get("rephraser_result") or data.get("llm_result") or sanitized_prompt
            
            if image_urls and len(image_urls) > 0:
                # 如果API返回了URL，我们可以直接使用
                remote_url = image_urls[0]
                
                # 也可以选择下载图像到本地
                try:
                    # 下载图像
                    img_response = requests.get(remote_url)
                    if img_response.status_code == 200:
                        # 生成文件名
                        image_filename = f"image_{int(self._get_timestamp())}_{hash(prompt)%10000}.png"
                        image_path = self.image_dir / image_filename
                        
                        # 保存图像
                        with open(image_path, "wb") as f:
                            f.write(img_response.content)
                        
                        return {
                            "status": "success",
                            "image_url": str(image_path),
                            "remote_url": remote_url,
                            "prompt": optimized_prompt
                        }
                    else:
                        # 如果无法下载，则直接返回远程URL
                        return {
                            "status": "success",
                            "image_url": remote_url,
                            "prompt": optimized_prompt
                        }
                except Exception as e:
                    logger.warning(f"下载图像失败，使用远程URL: {str(e)}")
                    return {
                        "status": "success",
                        "image_url": remote_url,
                        "prompt": optimized_prompt
                    }
            else:
                # 如果返回的是base64数据
                binary_data = data.get("binary_data_base64", [])
                if binary_data and len(binary_data) > 0:
                    # 生成文件名
                    image_filename = f"image_{int(self._get_timestamp())}_{hash(prompt)%10000}.png"
                    image_path = self.image_dir / image_filename
                    
                    # 保存图像
                    with open(image_path, "wb") as f:
                        f.write(base64.b64decode(binary_data[0]))
                    
                    return {
                        "status": "success",
                        "image_url": str(image_path),
                        "prompt": optimized_prompt
                    }
                else:
                    logger.error("图像生成响应中没有图像数据")
                    return {
                        "status": "error",
                        "error": "图像生成响应中没有图像数据"
                    }
                
        except Exception as e:
            logger.exception(f"图像生成过程中出错: {str(e)}")
            return {
                "status": "error",
                "error": f"图像生成过程中出错: {str(e)}"
            }
    
    def _get_style_prefix(self, style: str) -> str:
        """获取风格前缀
        
        Args:
            style: 图像风格
            
        Returns:
            str: 风格前缀
        """
        style_prefix_map = {
            "realistic": "写实风格，高清细节",
            "anime": "动漫风格，二次元",
            "painting": "绘画风格，艺术感",
            "sketch": "素描风格，黑白线条",
            "3d": "3D渲染，立体感"
        }
        
        return style_prefix_map.get(style.lower(), "写实风格")
    
    def _get_timestamp(self) -> int:
        """获取当前时间戳
        
        Returns:
            int: 时间戳
        """
        import time
        return int(time.time())
    
    @staticmethod
    def validate_api_key(access_key_id: str, secret_access_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """验证API密钥是否有效
        
        Args:
            access_key_id: 访问密钥ID
            secret_access_key: 访问密钥
            base_url: API基础URL（可选）
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        try:
            # 尝试生成一个简单的图像来验证
            service = ImageService(access_key_id, secret_access_key, base_url)
            result = service.generate_image("测试图像", size="256x256")
            
            if result.get("status") == "success":
                return {
                    "status": "success",
                    "is_valid": True,
                    "message": "API密钥有效"
                }
            else:
                return {
                    "status": "error",
                    "is_valid": False,
                    "message": f"API密钥无效: {result.get('error')}"
                }
                
        except Exception as e:
            logger.exception(f"验证API密钥过程中出错: {str(e)}")
            return {
                "status": "error",
                "is_valid": False,
                "message": f"验证API密钥过程中出错: {str(e)}"
            } 