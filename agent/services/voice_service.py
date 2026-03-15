"""语音服务模块，负责文本转语音功能

该模块利用火山引擎的大模型语音合成API，提供高自然度、情感化的语音合成服务。
支持对场景对话内容进行语音播放，提升沉浸感。
"""

import requests
import json
import logging
import base64
import time
import os
import uuid
import asyncio
import websockets
import struct
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union, BinaryIO

logger = logging.getLogger(__name__)

class VoiceService:
    """语音服务，负责文本转语音"""
    
    def __init__(self, app_id: str = None, token: str = None, llm_client = None, llm_model: str = None):
        """初始化语音服务
        
        Args:
            app_id: 火山引擎语音合成AppID
            token: 火山引擎语音合成Token（access_token）
            llm_client: LLM客户端，用于智能选择音色
            llm_model: LLM模型名称
        """
        self.app_id = app_id
        self.token = token
        self.http_api_url = "https://openspeech.bytedance.com/api/v1/tts"
        self.ws_api_url = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"
        
        # 旧的音色映射（兼容性保留）
        self.voices = {
            "default": "BV001_streaming",  # 默认免费音色
            "male": "BV002_streaming",  # 男声免费音色
            "female": "BV001_streaming",  # 女声免费音色
            "child": "BV001_streaming",  # 童声
            "anime": "BV001_streaming",  # 动漫配音
            "elder": "BV002_streaming"  # 老年声音
        }
        
        # 高级音色映射（需要权限）
        self.premium_voices = {
            "default": "zh_female_wanqudashu_moon_bigtts",  # 默认用户授权的音色 - 湾区大叔
            "male": "zh_male_beijingxiaoye_moon_bigtts",  # 北京小爷
            "female": "zh_female_daimengchuanmei_moon_bigtts",  # 呆萌川妹
            "child": "zh_male_shaonianzixin_moon_bigtts",  # 少年梓辛/Brayan
            "anime": "zh_female_sajiaonvyou_moon_bigtts",  # 撒娇学妹
            "elder": "zh_male_shenyeboke_moon_bigtts"  # 深夜播客
        }
        
        # 用户拥有的Moon音色列表（从控制台获取）
        self.moon_voices = [
            "zh_female_wanqudashu_moon_bigtts",  # 湾区大叔
            "zh_female_daimengchuanmei_moon_bigtts",  # 呆萌川妹 
            "zh_male_guozhoudege_moon_bigtts",  # 广州德哥
            "zh_male_beijingxiaoye_moon_bigtts",  # 北京小爷
            "zh_male_shaonianzixin_moon_bigtts",  # 少年梓辛/Brayan
            "zh_female_meilinvyou_moon_bigtts",  # 魅力女友
            "zh_male_shenyeboke_moon_bigtts",  # 深夜播客
            "zh_female_sajiaonvyou_moon_bigtts",  # 撒娇学妹
            "zh_female_yuanqinvyou_moon_bigtts",  # 撒娇女友
            "zh_male_haoyuxiaoge_moon_bigtts"  # 浩宇小哥
        ]
        
        # 创建音频缓存目录
        self.audio_cache_dir = Path("./data/audio_cache")
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 声音数据文件路径
        self.voice_data_path = Path("./data/voices.json")
        self.voice_data = self._load_voice_data()
        
        # LLM客户端和模型，用于智能选择音色
        self.llm_client = llm_client
        self.llm_model = llm_model
    
    def _load_voice_data(self) -> Dict[str, Any]:
        """加载声音数据
        
        Returns:
            Dict[str, Any]: 声音数据
        """
        try:
            if self.voice_data_path.exists():
                with open(self.voice_data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"声音数据文件不存在: {self.voice_data_path}")
                return {}
        except Exception as e:
            logger.exception(f"加载声音数据失败: {str(e)}")
            return {}
    
    def set_llm_client(self, llm_client, llm_model: str = None):
        """设置LLM客户端和模型
        
        Args:
            llm_client: LLM客户端
            llm_model: LLM模型名称
        """
        self.llm_client = llm_client
        if llm_model:
            self.llm_model = llm_model
    
    def set_app_id(self, app_id: str) -> None:
        """设置火山引擎语音合成AppID
        
        Args:
            app_id: 火山引擎语音合成AppID
        """
        self.app_id = app_id
    
    def set_token(self, token: str) -> None:
        """设置火山引擎语音合成Token（access_token）
        
        Args:
            token: 火山引擎语音合成Token
        """
        if token:
            # 清理token格式
            clean_token = token
            if clean_token.startswith("Bearer"):
                clean_token = clean_token.replace("Bearer", "").strip()
                if clean_token.startswith(";"):
                    clean_token = clean_token[1:].strip()
            
            # 验证token格式
            if len(clean_token) < 10:  # 正常token应该很长
                logger.warning(f"警告: 设置的Token长度异常短 ({len(clean_token)}字符)，可能不是有效的Token")
                logger.warning("正确的Token通常是一个很长的字符串，如: ey123...abc")
                logger.warning("请确保您使用的是火山引擎控制台提供的access_token，而非API Key或其他凭证")
            
            logger.info(f"设置语音服务Token: {clean_token[:5]}*** (长度: {len(clean_token)})")
            self.token = clean_token  # 存储已清理的token
        else:
            logger.warning("设置的Token为空")
            self.token = None
    
    def get_voice_list(self) -> List[str]:
        """获取可用的语音列表
        
        Returns:
            List[str]: 可用的语音列表
        """
        if self.voice_data and 'categories' in self.voice_data:
            # 返回所有分类中的所有音色
            voice_types = []
            for category in self.voice_data['categories'].values():
                for voice in category:
                    voice_types.append(voice['voice_type'])
            return voice_types
        else:
            # 如果没有加载声音数据，返回旧的音色列表
            return list(self.voices.values())
    
    async def _generate_speech_websocket(self, text: str, voice_type: str, 
                                        speed: float = 1.0, 
                                        format: str = "mp3",
                                        output_file: str = None,
                                        emotion: str = None) -> Optional[str]:
        """使用Websocket API生成语音（支持流式合成）
        
        Args:
            text: 文本内容
            voice_type: 语音类型
            speed: 语速，范围 0.5-2.0
            format: 音频格式，可选值: mp3, wav, pcm, ogg_opus
            output_file: 输出文件路径，如果不指定则自动生成
            emotion: 情感类型，仅部分音色支持
            
        Returns:
            Optional[str]: 生成的音频文件路径，失败返回None
        """
        if not self.app_id or not self.token:
            logger.error("未设置火山引擎语音合成AppID或Token，无法生成语音")
            return None
        
        # 备用免费音色，按优先级排序
        free_voice_types = ["BV001_streaming", "BV002_streaming", "BV003_streaming", "BV004_streaming", "BV005_streaming"]
        
        # 如果用户使用的本来就是免费音色之一，则在失败时尝试其他免费音色
        if voice_type in free_voice_types:
            free_voice_types.remove(voice_type)
            # 将其他免费音色按顺序排列
            free_voice_types = [voice_type] + free_voice_types
        
        # 依次尝试所有音色
        for current_voice in [voice_type] + ([] if voice_type in free_voice_types else free_voice_types):
            try:
                # 当前尝试的不是第一个音色时，输出信息
                if current_voice != voice_type:
                    logger.info(f"尝试使用替代免费音色: {current_voice}")
            
                # 生成唯一请求ID
                req_id = str(uuid.uuid4())
                
                # 构建请求数据
                payload = {
                    "app": {
                        "appid": self.app_id,
                        "token": "placeholder_token",  # 请求体中的token，可以是任意非空字符串
                        "cluster": "volcano_tts"
                    },
                    "user": {
                        "uid": f"user_{int(time.time())}"
                    },
                    "audio": {
                        "voice_type": current_voice,
                        "encoding": format,
                        "speed_ratio": speed,
                    },
                    "request": {
                        "reqid": req_id,
                        "text": text,
                        "operation": "submit"  # 使用submit进行流式合成
                    }
                }
                
                # 如果指定了情感，并且是支持情感的音色
                if emotion and '_emo_' in current_voice:
                    payload["audio"]["enable_emotion"] = True
                    payload["audio"]["emotion"] = emotion
                    payload["audio"]["emotion_scale"] = 4.0  # 默认强度为4
                
                # 如果没有指定输出文件，则自动生成文件名
                if not output_file:
                    emotion_part = f"_{emotion}" if emotion else ""
                    cache_key = f"{hash(text)}_{current_voice}{emotion_part}_{speed}_{format}"
                    current_output_file = str(self.audio_cache_dir / f"{cache_key}.{format}")
                else:
                    current_output_file = output_file
                
                # 检查缓存
                if os.path.exists(current_output_file):
                    logger.info(f"使用缓存的语音文件: {current_output_file}")
                    return current_output_file
                
                # 创建临时文件
                temp_file = current_output_file + ".tmp"
                chunks_received = 0
                
                # 创建websocket连接
                headers = {}
                if self.token:
                    # 按照文档格式设置认证头 - 必须严格按照 "Bearer; {token}" 格式（注意分号后有空格）
                    headers["Authorization"] = f"Bearer; {self.token}"
                    logger.info(f"认证头格式: Bearer; token (token长度: {len(self.token)})")
                
                logger.info(f"正在连接Websocket API: {self.ws_api_url}")
                logger.info(f"认证头: {headers.get('Authorization', '未设置')[:15]}...")
                logger.info(f"使用音色: {current_voice}")
                
                # 使用临时文件写入音频数据
                with open(temp_file, "wb") as audio_file:
                    try:
                        async with websockets.connect(self.ws_api_url, extra_headers=headers) as ws:
                            # 发送请求
                            await ws.send(json.dumps(payload))
                            logger.info(f"请求已发送，等待响应，文本长度: {len(text)}")
                            
                            # 接收响应
                            while True:
                                try:
                                    response = await ws.recv()
                                    
                                    # 解析二进制响应
                                    if isinstance(response, bytes):
                                        # 解析头部
                                        header = response[:4]
                                        # 解析版本、头部大小、消息类型等
                                        version = (header[0] >> 4) & 0xF
                                        header_size = (header[0] & 0xF) * 4
                                        msg_type = (header[1] >> 4) & 0xF
                                        flags = header[1] & 0xF
                                        
                                        # 如果是音频响应
                                        if msg_type == 0xB:  # 0b1011 - Audio-only server response
                                            # 写入音频数据（跳过头部）
                                            audio_file.write(response[header_size:])
                                            chunks_received += 1
                                            
                                            # 检查是否是最后一个音频块
                                            if flags in [0x2, 0x3]:  # 0b0010 or 0b0011
                                                logger.info(f"收到最后一个音频块，合成完成")
                                                break
                                        # 如果是错误消息
                                        elif msg_type == 0xF:  # 0b1111 - Error message
                                            error_payload = response[header_size:]
                                            if error_payload:
                                                try:
                                                    error_json = json.loads(error_payload.decode('utf-8'))
                                                    logger.error(f"收到错误消息: {error_json}")
                                                    
                                                    # 判断是否是资源权限错误
                                                    if 'requested resource not granted' in str(error_json):
                                                        logger.error("资源权限错误，尝试使用其他免费音色")
                                                        break  # 跳出接收循环，尝试下一个音色
                                                except:
                                                    logger.error(f"收到无法解析的错误消息")
                                            break
                                    else:
                                        try:
                                            # 尝试解析JSON响应
                                            json_resp = json.loads(response)
                                            if json_resp.get("code") != 0:
                                                logger.error(f"收到错误响应: {json_resp}")
                                                break
                                        except:
                                            logger.warning(f"收到无法解析的响应: {response[:100]}")
                                except websockets.exceptions.ConnectionClosedError as e:
                                    logger.error(f"WebSocket连接关闭: {str(e)}")
                                    if "1008" in str(e):
                                        logger.error("策略违规，可能是认证失败或权限不足")
                                        logger.error(f"认证头: {headers.get('Authorization', '未设置').split(';')[0]}; ***")
                                        logger.error(f"请确保token格式正确，应为 'Bearer; {self.token[:5]}...'")
                                        
                                        # 检查是否是访问权限问题
                                        if "access denied" in str(e).lower() or "extract request resource id" in str(e).lower() or "requested resource not granted" in str(e).lower():
                                            logger.info("资源权限错误，尝试使用其他免费音色")
                                            # 这里不直接返回_retry_with_free_voice，因为我们使用了循环尝试所有音色
                                            break  # 跳出接收循环，尝试下一个音色
                                    elif "1011" in str(e):
                                        logger.error("服务器内部错误，请稍后重试")
                                        break
                                    elif "403" in str(e) or "unauthorized" in str(e).lower():
                                        logger.error("认证失败，请检查token是否有效")
                                        logger.error(f"认证头: {headers.get('Authorization', '未设置').split(';')[0]}; ***")
                                        # 认证错误，直接返回None
                                        return None
                                    break
                                except Exception as e:
                                    logger.error(f"接收响应时出错: {str(e)}")
                                    break
                    except Exception as e:
                        logger.exception(f"WebSocket通信失败: {str(e)}")
                        # 可能是网络错误，继续尝试下一个音色
                        continue
                            
                # 如果成功接收到音频数据
                if chunks_received > 0:
                    # 重命名临时文件为最终文件
                    os.rename(temp_file, current_output_file)
                    logger.info(f"语音生成成功，保存到: {current_output_file}")
                    return current_output_file
                else:
                    # 删除临时文件
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except:
                        pass
                    # 没有收到音频数据，尝试下一个音色
                    continue
                    
            except Exception as e:
                logger.exception(f"Websocket生成语音失败: {str(e)}")
                # 删除可能存在的临时文件
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                # 尝试下一个音色
                continue
        
        # 所有音色都尝试失败
        logger.error("所有音色尝试都失败")
        return None
    
    def generate_speech(self, text: str, voice_type: str = "default", 
                       speed: float = 1.0, 
                       format: str = "mp3",
                       return_path: bool = True,
                       emotion: str = None) -> Optional[str]:
        """生成语音
        
        Args:
            text: 文本内容
            voice_type: 语音类型，可选值: default, male, female, child, anime, elder
                        或直接传入voice_type值
            speed: 语速，范围 0.5-2.0
            format: 音频格式，可选值: mp3, wav, pcm
            return_path: 是否返回文件路径，否则返回Base64编码
            emotion: 情感类型，仅部分音色支持
            
        Returns:
            Optional[str]: 生成的音频文件路径或Base64编码，失败返回None
        """
        if not self.app_id:
            logger.error("未设置火山引擎语音合成AppID，无法生成语音")
            return None
        
        if not text:
            logger.warning("文本内容为空，跳过语音生成")
            return None
            
        # 获取语音类型
        # 如果voice_type是简称，则根据用户权限选择高级音色或免费音色
        if voice_type in self.premium_voices:
            # 首先尝试高级音色
            voice = self.premium_voices.get(voice_type)
        elif voice_type in self.voices:
            # 如果没有指定高级音色或无权限，则使用免费音色
            voice = self.voices.get(voice_type)
        else:
            # 直接使用传入的voice_type
            voice = voice_type
        
        # 计算缓存文件名
        emotion_part = f"_{emotion}" if emotion else ""
        cache_key = f"{hash(text)}_{voice}{emotion_part}_{speed}_{format}"
        cache_path = self.audio_cache_dir / f"{cache_key}.{format}"
        
        # 检查缓存
        if cache_path.exists():
            logger.info(f"使用缓存的语音文件: {cache_path}")
            return str(cache_path) if return_path else self._file_to_base64(cache_path)
        
        # 准备按优先级试用的音色列表
        
        # 1. 首先使用用户请求的音色
        voice_types = [voice]
        
        # 2. 如果是简称且用户拥有对应类型的高级音色，则添加到列表中
        if voice_type in self.premium_voices and voice not in voice_types:
            voice_types.append(self.premium_voices[voice_type])
        
        # 3. 然后是用户所有授权的Moon音色
        for moon_voice in self.moon_voices:
            if moon_voice not in voice_types:
                voice_types.append(moon_voice)
        
        # 4. 最后是备用免费音色
        free_voice_types = ["BV001_streaming", "BV002_streaming", "BV003_streaming", "BV004_streaming", "BV005_streaming"]
        for free_voice in free_voice_types:
            if free_voice not in voice_types:
                voice_types.append(free_voice)
        
        # 尝试使用HTTP API，按照音色优先级依次尝试
        for current_voice in voice_types:
            try:
                # 当前尝试的不是第一个音色时，输出信息
                if current_voice != voice:
                    logger.info(f"尝试使用替代音色: {current_voice}")
                
                # 生成唯一请求ID
                req_id = str(uuid.uuid4())
                
                # 构建请求数据
                payload = {
                    "app": {
                        "appid": self.app_id,
                        "token": "placeholder_token",  # 请求体中的token，可以是任意非空字符串
                        "cluster": "volcano_tts"
                    },
                    "user": {
                        "uid": f"user_{int(time.time())}"
                    },
                    "audio": {
                        "voice_type": current_voice,
                        "encoding": format,
                        "speed_ratio": speed,
                    },
                    "request": {
                        "reqid": req_id,
                        "text": text,
                        "operation": "query"  # HTTP API只能使用query
                    }
                }
                
                # 如果指定了情感，并且是支持情感的音色
                if emotion and ('_emo_' in current_voice or '_moon_' in current_voice):
                    payload["audio"]["enable_emotion"] = True
                    payload["audio"]["emotion"] = emotion
                    payload["audio"]["emotion_scale"] = 4.0  # 默认强度为4
                
                # 设置请求头
                headers = {
                    "Content-Type": "application/json"
                }
                
                # 添加认证头
                if self.token:
                    # 按照文档格式设置认证头 - 必须严格按照 "Bearer; {token}" 格式（注意分号后有空格）
                    headers["Authorization"] = f"Bearer; {self.token}"
                    logger.info(f"认证头格式: Bearer; token (token长度: {len(self.token)})")
                
                # 调用API
                logger.info(f"正在生成语音，文本长度: {len(text)}")
                logger.info(f"认证头: {headers.get('Authorization', '未设置')[:15]}...")
                logger.info(f"使用音色: {current_voice}")
                response = requests.post(self.http_api_url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        audio_data = base64.b64decode(data.get("data", ""))
                        
                        # 保存到文件
                        with open(cache_path, "wb") as f:
                            f.write(audio_data)
                        
                        logger.info(f"语音生成成功，保存到: {cache_path}")
                        return str(cache_path) if return_path else data.get("data", "")
                    else:
                        logger.error(f"语音生成失败: {data.get('message')}, 错误码: {data.get('code')}")
                        # 如果是当前音色的最后一次尝试，继续尝试下一个音色
                        continue
                else:
                    logger.error(f"API请求失败，状态码: {response.status_code}")
                    if response.status_code == 403:
                        logger.error("403错误通常表示认证失败，请检查token是否正确设置")
                        # 分析403错误的详细原因
                        try:
                            error_data = response.json()
                            error_message = error_data.get('message', '')
                            logger.error(f"错误详情: {error_data}")
                            
                            if 'authenticate request' in error_message or 'load grant' in error_message:
                                logger.error("认证错误: token格式不正确或未找到")
                                logger.error("请确保token不包含引号，没有前后空格，且格式正确")
                                logger.error(f"当前认证头: {headers.get('Authorization', '')[:15]}...")
                                logger.error(f"正确格式应为: Bearer; {self.token[:5]}...")
                                # 认证错误，尝试下一个音色没有意义，直接返回失败
                                break
                            elif 'requested resource not granted' in error_message or 'access denied' in error_message or 'extract request resource id' in error_message:
                                logger.error("访问被拒绝: 可能是无权限访问该音色资源")
                                logger.error(f"尝试其他音色...")
                                # 资源权限错误，尝试下一个音色
                                continue
                            elif 'quota exceeded' in error_message:
                                logger.error("超出配额: 您的账户可能已超出使用配额限制")
                                # 配额问题，尝试下一个音色
                                continue
                            else:
                                logger.error(f"未知403错误: {error_message}")
                                logger.error(f"当前认证头: {headers.get('Authorization', '')[:15]}...")
                                # 未知错误，尝试下一个音色
                                continue
                        except Exception as e:
                            logger.error(f"解析错误响应失败: {str(e)}")
                            logger.error(f"响应内容: {response.text[:200]}")
                            # 解析错误，尝试下一个音色
                            continue
                    else:
                        # 其他状态码的错误
                        try:
                            error_data = response.json()
                            logger.error(f"错误详情: {error_data}")
                            
                            # 处理401错误
                            if response.status_code == 401:
                                error_message = error_data.get('message', '')
                                if 'load grant' in error_message or 'requested grant not found' in error_message:
                                    logger.error("认证失败: Token无效或格式错误")
                                    logger.error("请确保您使用的是正确的Token，而不是API Key或其他凭证")
                                    logger.error("火山引擎语音合成需要使用专门的access_token，而非API Key")
                                    logger.error("请登录火山引擎控制台获取正确的Token: https://console.volcengine.com/")
                                    # 认证错误，尝试下一个音色没有意义，直接返回失败
                                    break
                                else:
                                    logger.error(f"认证失败: {error_message}")
                                    # 其他认证错误，尝试下一个音色
                                    continue
                        except:
                            logger.error(f"响应内容: {response.text[:200]}")
                            # 解析错误，尝试下一个音色
                            continue
            
            except Exception as e:
                logger.exception(f"HTTP生成语音失败: {str(e)}")
                # 继续尝试下一个音色
                continue
        
        # 如果所有尝试都失败，返回None
        return None
    
    def extract_dialogues(self, scene_text: str) -> List[Dict[str, Any]]:
        """从场景文本中提取对话
        
        Args:
            scene_text: 场景文本
            
        Returns:
            List[Dict[str, Any]]: 提取的对话列表，每个对话包含说话人和内容
        """
        logger.info(f"开始从场景文本中提取对话，文本长度: {len(scene_text)}")
        
        # 检查是否有LLM客户端用于智能提取
        if self.llm_client and self.llm_model:
            try:
                logger.info("使用LLM智能提取对话")
                return self._extract_dialogues_with_llm(scene_text)
            except Exception as e:
                logger.warning(f"LLM提取对话失败，回退到规则提取: {str(e)}")
                # 如果智能提取失败，回退到规则提取
        
        # 规则提取逻辑
        dialogues = []
        
        # 使用中文冒号和英文冒号切分句子，找出对话
        lines = scene_text.split('\n')
        for line in lines:
            # 移除多余空格
            line = line.strip()
            if not line:
                continue
            
            # 检查是否包含对话标识（中文冒号或英文冒号）
            if '：' in line or ': ' in line:
                delimiter = '：' if '：' in line else ': '
                parts = line.split(delimiter, 1)
                
                if len(parts) == 2:
                    speaker, content = parts
                    speaker = speaker.strip()
                    content = content.strip()
                    
                    # 移除引号和其他标点
                    content = content.strip('"\'""''。.,!?！？，、》《')
                    
                    # 检查内容是否为空
                    if speaker and content:
                        dialogues.append({
                            'speaker': speaker,
                            'content': content
                        })
        
        logger.info(f"规则提取到 {len(dialogues)} 段对话")
        return dialogues
    
    def _extract_dialogues_with_llm(self, scene_text: str) -> List[Dict[str, Any]]:
        """使用LLM智能提取场景中的对话
        
        Args:
            scene_text: 场景文本
            
        Returns:
            List[Dict[str, Any]]: 提取的对话列表
        """
        # 检查LLM客户端是否可用
        if not self.llm_client:
            logger.error("LLM客户端未设置，无法使用智能提取")
            return []
            
        if not self.llm_model:
            logger.warning("LLM模型未设置，使用默认模型")
            self.llm_model = "deepseek-chat"
            
        # 记录详细信息
        logger.info(f"使用LLM智能提取对话，文本长度: {len(scene_text)}")
        logger.info(f"LLM客户端: {type(self.llm_client).__name__}, 模型: {self.llm_model}")
        
        # 构建提示
        prompt = f"""请从以下场景文本中提取所有对话内容。以JSON格式返回，包含说话人(speaker)和对话内容(content)。
只提取明确的对话(带有说话人的内容)，不要提取旁白和环境描述。

场景文本:
{scene_text}

请按以下格式返回(仅返回JSON，不要其他文字):
[
  {{"speaker": "角色A", "content": "对话内容1"}},
  {{"speaker": "角色B", "content": "对话内容2"}}
]

如果没有对话，返回空数组[]。"""

        # 调用LLM提取对话
        try:
            logger.info("发送对话提取请求到DeepSeek...")
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            logger.info(f"收到DeepSeek响应，长度: {len(content)}")
            logger.info(f"响应前100字符: {content[:100]}")
            
            # 尝试解析JSON
            try:
                # 提取JSON部分（防止模型输出额外内容）
                import re
                json_pattern = r'\[.*\]'
                match = re.search(json_pattern, content, re.DOTALL)
                
                if match:
                    content = match.group(0)
                    logger.info(f"提取JSON部分成功，长度: {len(content)}")
                
                dialogues = json.loads(content)
                logger.info(f"LLM成功提取到 {len(dialogues)} 段对话")
                return dialogues
            except Exception as e:
                logger.warning(f"解析LLM提取的对话失败: {str(e)}")
                # 尝试更宽松的解析方式
                try:
                    # 移除可能干扰JSON解析的文字
                    content = content.replace("```json", "").replace("```", "")
                    dialogues = json.loads(content)
                    logger.info(f"二次尝试：LLM成功提取到 {len(dialogues)} 段对话")
                    return dialogues
                except Exception as e2:
                    logger.error(f"二次尝试解析JSON也失败: {str(e2)}")
                    logger.error(f"JSON内容: {content}")
                    return []
        except Exception as e:
            logger.exception(f"调用LLM提取对话失败: {str(e)}")
            return []
    
    def select_voice_for_dialogue(self, dialogue: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
        """使用LLM为对话选择合适的音色
        
        Args:
            dialogue: 对话信息，包含speaker和content
            scene: 场景信息
            
        Returns:
            Dict[str, Any]: 更新后的对话信息，包含voice_type和emotion
        """
        dialogue_result = dialogue.copy()
        speaker = dialogue.get('speaker', '')
        content = dialogue.get('content', '')
        
        if not speaker or not content:
            logger.warning(f"对话信息不完整，无法选择音色: {dialogue}")
            return dialogue_result
        
        try:
            # 检查是否有LLM客户端用于智能选择
            if self.llm_client and self.llm_model:
                try:
                    # 构造提示
                    prompt = f"""请为以下对话选择最合适的声音类型和情感状态。小说场景中的角色"{speaker}"说: "{content}"。
                    
场景背景: 
{scene.get('narrative', '')[:200]}...

请考虑角色的性别、年龄、性格和当前情感状态，从以下选项中为"{speaker}"角色选择最合适的声音类型:

1. zh_female_qingxin_bigtts - 清新女声
2. zh_female_yueyue_bigtts - 悦悦女声
3. zh_female_shaonianyin_bigtts - 少年音女声
4. zh_female_yunyun_bigtts - 云韵女声
5. zh_male_qingxin_bigtts - 清新男声
6. zh_male_shaonian_bigtts - 少年男声
7. zh_male_yifei_bigtts - 姨夫男声
8. zh_child_chengcheng_bigtts - 程程童声
9. zh_older_huwei_bigtts - 胡伟老年声

还请选择对话中的情感状态（高兴、悲伤、愤怒、平静等）

请仅返回一个JSON对象，格式如下：
{{"voice_type": "选择的声音类型", "emotion": "情感状态", "reasoning": "选择原因"}}"""

                    # 调用LLM选择音色
                    response = self.llm_client.chat.completions.create(
                        model=self.llm_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=300
                    )
                    
                    content = response.choices[0].message.content
                    
                    # 尝试解析JSON
                    try:
                        # 提取JSON部分
                        import re
                        json_pattern = r'\{.*\}'
                        match = re.search(json_pattern, content, re.DOTALL)
                        
                        if match:
                            content = match.group(0)
                        
                        result = json.loads(content)
                        
                        # 更新对话信息
                        dialogue_result['voice_type'] = result.get('voice_type')
                        dialogue_result['emotion'] = result.get('emotion')
                        dialogue_result['voice_reasoning'] = result.get('reasoning')
                        
                        logger.info(f"为'{speaker}'选择音色: {result.get('voice_type')}, 情感: {result.get('emotion')}")
                        return dialogue_result
                    except Exception as e:
                        logger.warning(f"解析LLM选择的音色失败: {str(e)}")
                except Exception as e:
                    logger.warning(f"LLM选择音色失败: {str(e)}")
            
            # 如果智能选择失败，回退到基础选择
            voice_type = self._select_voice_for_speaker(speaker)
            dialogue_result['voice_type'] = voice_type
            dialogue_result['emotion'] = "neutral"  # 默认情感
            
            return dialogue_result
        except Exception as e:
            logger.exception(f"为对话选择音色失败: {str(e)}")
            # 设置默认音色
            dialogue_result['voice_type'] = "zh_female_shaonianyin_bigtts"
            dialogue_result['emotion'] = "neutral"
            return dialogue_result
    
    def generate_audio_for_scene(self, scene: Dict[str, Any]) -> Dict[str, Any]:
        """为场景生成语音
        
        Args:
            scene: 场景信息
            
        Returns:
            Dict[str, Any]: 语音信息，包含每段对话的音频路径
        """
        result = {
            "status": "success",
            "dialogues": []
        }
        
        # 从场景中提取对话
        narrative = scene.get('narrative', '')
        logger.info(f"开始从场景提取对话，场景ID: {scene.get('interaction_id', 'unknown')}")
        logger.info(f"场景文本长度: {len(narrative)}")
        
        dialogues = self.extract_dialogues(narrative)
        logger.info(f"提取到对话数量: {len(dialogues)}")
        
        # 为每段对话生成语音
        for i, dialogue in enumerate(dialogues):
            speaker = dialogue.get('speaker', '')
            content = dialogue.get('content', '')
            
            if not speaker or not content:
                logger.warning(f"跳过不完整的对话: {dialogue}")
                continue
            
            try:
                # 更新对话，选择合适的音色和情感
                dialogue_with_voice = self.select_voice_for_dialogue(dialogue, scene)
                
                # 获取音色和情感
                voice_type = dialogue_with_voice.get('voice_type')
                emotion = dialogue_with_voice.get('emotion', 'neutral')
                
                if not voice_type:
                    logger.warning(f"未找到适合'{speaker}'的音色，使用默认音色")
                    voice_type = "zh_female_shaonianyin_bigtts"
                
                # 检查是否是情感型音色
                has_emotion_support = '_emo_' in voice_type if voice_type else False
                
                # 生成语音
                logger.info(f"为'{speaker}'的对话生成语音，音色: {voice_type}, 情感: {emotion if has_emotion_support else '不支持情感'}")
                
                audio_path = self.generate_speech(
                    text=content,
                    voice_type=voice_type,
                    speed=1.0,
                    format="mp3",
                    emotion=emotion if has_emotion_support else None
                )
                
                if audio_path:
                    # 添加音频路径到对话信息
                    dialogue_with_voice['audio_path'] = audio_path
                    dialogue_with_voice['index'] = i
                    
                    # 添加到结果中
                    result['dialogues'].append(dialogue_with_voice)
                    logger.info(f"对话语音生成成功: {audio_path}")
                else:
                    logger.warning(f"对话语音生成失败: '{content}'")
            except Exception as e:
                logger.exception(f"为对话生成语音失败: {str(e)}")
        
        # 如果没有生成任何语音，设置失败状态
        if len(result['dialogues']) == 0:
            if len(dialogues) > 0:
                result['status'] = 'error'
                result['message'] = '对话语音生成失败'
            else:
                result['status'] = 'warning'
                result['message'] = '未检测到任何对话'
        
        return result
    
    def _select_voice_for_speaker(self, speaker: str) -> str:
        """根据说话者选择合适的语音类型（基本选择方法，作为备用）
        
        Args:
            speaker: 说话者名称
            
        Returns:
            str: 语音类型
        """
        speaker = speaker.lower()
        
        # 根据角色特征选择声音
        if any(keyword in speaker for keyword in ['爸', '父', '公', '男', '大叔', '叔', '爷', '王', '李', '张']):
            return "BV002_streaming"  # 男声免费音色
        elif any(keyword in speaker for keyword in ['妈', '母', '婆', '女', '小姐', '姐', '妹', '阿姨', '王夫人']):
            return "BV001_streaming"  # 女声免费音色
        elif any(keyword in speaker for keyword in ['小', '儿', '童', '孩']):
            return "BV001_streaming"  # 童声免费音色
        elif any(keyword in speaker for keyword in ['老', '爷爷', '奶奶', '姥', '翁']):
            return "BV002_streaming"  # 老年免费音色
        elif any(keyword in speaker for keyword in ['机器', '人工', 'AI', '智能', '机械']):
            return "BV001_streaming"  # 动漫配音免费音色
        
        # 默认使用女声
        return "BV001_streaming"  # 默认免费音色
    
    def _file_to_base64(self, file_path: str) -> str:
        """将文件转换为Base64编码
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: Base64编码
        """
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.exception(f"文件转Base64失败: {str(e)}")
            return ""
    
    def generate_speech_stream(self, text: str, voice_type: str = "default", 
                              speed: float = 1.0, 
                              format: str = "mp3",
                              emotion: str = None) -> Optional[str]:
        """流式生成语音（使用异步API但同步调用）
        
        Args:
            text: 文本内容
            voice_type: 语音类型，可选值: default, male, female, child, anime, elder
                        或直接传入voice_type值
            speed: 语速，范围 0.5-2.0
            format: 音频格式，可选值: mp3, wav, pcm, ogg_opus
            emotion: 情感类型，仅部分音色支持
            
        Returns:
            Optional[str]: 生成的音频文件路径，失败返回None
        """
        if not self.app_id:
            logger.error("未设置火山引擎语音合成AppID，无法生成语音")
            return None
        
        if not text:
            logger.warning("文本内容为空，跳过语音生成")
            return None
            
        # 获取语音类型
        # 如果是voice_type是字典中的简称，则查表转换
        if voice_type in self.voices:
            voice = self.voices.get(voice_type)
        else:
            # 否则直接使用传入的voice_type
            voice = voice_type
        
        # 计算缓存文件名
        emotion_part = f"_{emotion}" if emotion else ""
        cache_key = f"{hash(text)}_{voice}{emotion_part}_{speed}_{format}"
        cache_path = self.audio_cache_dir / f"{cache_key}.{format}"
        
        # 检查缓存
        if cache_path.exists():
            logger.info(f"使用缓存的语音文件: {cache_path}")
            return str(cache_path)
        
        # 创建事件循环并运行WebSocket请求
        try:
            # 检查当前是否有活动的事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # 运行WebSocket请求
            result = loop.run_until_complete(
                self._generate_speech_websocket(
                    text=text,
                    voice_type=voice,
                    speed=speed,
                    format=format,
                    output_file=str(cache_path),
                    emotion=emotion
                )
            )
            return result
            
        except Exception as e:
            logger.exception(f"流式生成语音失败: {str(e)}")
            return None
    
    def debug_auth_info(self) -> Dict[str, Any]:
        """返回认证信息用于调试
        
        Returns:
            Dict[str, Any]: 认证信息
        """
        return {
            "app_id": self.app_id,
            "token_set": self.token is not None,
            "token_length": len(self.token) if self.token else 0,
            "token_prefix": self.token[:5] + "***" if self.token and len(self.token) > 5 else None,
            "auth_header": f"Bearer;{self.token[:5]}***" if self.token and len(self.token) > 5 else None,
            "auth_header_format": "Bearer;{token}" if self.token else None
        }
    
    def test_token(self) -> Dict[str, Any]:
        """测试令牌是否有效
        
        Returns:
            Dict[str, Any]: 测试结果
        """
        if not self.app_id or not self.token:
            return {
                "status": "error",
                "message": "未设置AppID或Token",
                "details": {
                    "app_id_set": self.app_id is not None,
                    "token_set": self.token is not None
                }
            }
        
        # 构建最简单的请求
        req_id = str(uuid.uuid4())
        payload = {
            "app": {
                "appid": self.app_id,
                "token": "placeholder_token",  # 这里是请求体中的token，可以是任意非空字符串
                "cluster": "volcano_tts"
            },
            "user": {
                "uid": f"user_{int(time.time())}"
            },
            "audio": {
                "voice_type": "BV001_streaming",  # 使用免费音色
                "encoding": "mp3",
                "speed_ratio": 1.0,
            },
            "request": {
                "reqid": req_id,
                "text": "测试语音合成",
                "operation": "query"
            }
        }
        
        # 设置请求头 - 必须严格按照 "Bearer; {token}" 格式，这里的token是真正的认证token
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer; {self.token}"
        }
        
        # 尝试请求API
        try:
            logger.info(f"测试令牌有效性, AppID: {self.app_id[:5]}***, Token长度: {len(self.token)}")
            logger.info(f"认证头: {headers['Authorization'].split(';')[0]};***")
            logger.info(f"使用音色: {payload['audio']['voice_type']}")
            
            response = requests.post(self.http_api_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    return {
                        "status": "success",
                        "message": "令牌有效",
                        "details": {
                            "response_code": data.get("code"),
                            "auth_header": f"{headers['Authorization'].split(';')[0]}; ***",
                            "app_id": f"{self.app_id[:5]}***",
                            "token_length": len(self.token),
                            "voice_type": payload['audio']['voice_type']
                        }
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"API返回错误: {data.get('message')}",
                        "code": data.get("code"),
                        "details": {
                            "response": data,
                            "auth_header": f"{headers['Authorization'].split(';')[0]}; ***",
                            "voice_type": payload['audio']['voice_type']
                        }
                    }
            else:
                # 尝试解析错误
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', '')
                    
                    details = {
                        "status_code": response.status_code,
                        "error_data": error_data,
                        "auth_header_format": f"{headers['Authorization'].split(';')[0]}; ***",
                        "voice_type": payload['audio']['voice_type']
                    }
                    
                    if response.status_code == 403:
                        if 'authenticate request' in error_message or 'load grant' in error_message:
                            return {
                                "status": "error",
                                "message": "认证错误: token格式不正确或未找到",
                                "details": details
                            }
                        elif 'access denied' in error_message:
                            return {
                                "status": "error",
                                "message": "访问被拒绝: 可能是token无效或无权限访问该资源",
                                "details": details
                            }
                        elif 'quota exceeded' in error_message:
                            return {
                                "status": "error",
                                "message": "超出配额: 您的账户可能已超出使用配额限制",
                                "details": details
                            }
                        elif 'extract request resource id' in error_message:
                            return {
                                "status": "error",
                                "message": "资源ID提取失败: 可能是token无效或无权限访问该资源",
                                "details": details
                            }
                        elif 'requested resource not granted' in error_message:
                            return {
                                "status": "error",
                                "message": "资源访问权限不足: 您的账户没有访问此语音资源的权限",
                                "details": details,
                                "solution": "请在火山引擎控制台中确认您的账户已开通语音合成服务，并有权限使用所选音色。您可能需要先购买或开通相应的服务包。"
                            }
                        else:
                            return {
                                "status": "error",
                                "message": f"未知403错误: {error_message}",
                                "details": details
                            }
                    elif response.status_code == 401:
                        if 'load grant' in error_message or 'requested grant not found' in error_message:
                            return {
                                "status": "error",
                                "message": "认证失败: Token无效或格式错误",
                                "details": details
                            }
                    
                    return {
                        "status": "error",
                        "message": f"请求失败: HTTP {response.status_code}",
                        "details": details
                    }
                except:
                    return {
                        "status": "error",
                        "message": f"请求失败: HTTP {response.status_code}",
                        "details": {
                            "status_code": response.status_code,
                            "response_text": response.text[:200],
                            "auth_header": f"{headers['Authorization'].split(';')[0]}; ***"
                        }
                    }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"请求异常: {str(e)}",
                "details": {
                    "exception": str(e),
                    "auth_header": f"{headers['Authorization'].split(';')[0]}; ***"
                }
            }
    
    def validate_token(self) -> Dict[str, Any]:
        """验证Token格式是否合理
        
        Returns:
            Dict[str, Any]: 验证结果
        """
        if not self.token:
            return {
                "status": "error",
                "message": "未设置Token",
                "details": {
                    "token_set": False
                }
            }
            
        # 检查Token长度
        if len(self.token) < 10:
            return {
                "status": "warning",
                "message": "Token长度异常短，可能不是有效的Token",
                "details": {
                    "token_length": len(self.token),
                    "token_prefix": self.token[:5] + "***" if len(self.token) > 5 else self.token
                }
            }
            
        # 检查Token格式 - 通常是JWT格式 (eyJ开头)
        if not self.token.startswith("eyJ"):
            # 不是标准JWT格式，但可能是其他有效格式
            return {
                "status": "warning",
                "message": "Token不是标准的JWT格式，但可能仍然有效",
                "details": {
                    "token_length": len(self.token),
                    "token_prefix": self.token[:5] + "***" if len(self.token) > 5 else self.token,
                    "expected_prefix": "eyJ..."
                }
            }
            
        # 看起来是有效的Token格式
        return {
            "status": "success",
            "message": "Token格式看起来合理",
            "details": {
                "token_length": len(self.token),
                "token_prefix": self.token[:5] + "***"
            }
        } 