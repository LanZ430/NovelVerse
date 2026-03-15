from typing import Dict, Any, List, Optional
import logging
import json
from pathlib import Path
import re
from .base_agent import BaseAgent
from openai import OpenAI

logger = logging.getLogger(__name__)

class KnowledgeAgent(BaseAgent):
    """知识提取代理，负责分析文本并提取角色、设定和情节信息"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化知识提取代理
        
        Args:
            config: 配置信息，包括：
                - data_dir: 数据存储目录
                - llm_api_key: 大语言模型API密钥
                - llm_base_url: 大语言模型API基础URL
                - llm_model: 大语言模型名称
        """
        super().__init__(config)
        self.data_dir = Path(self.config.get('data_dir', './data'))
        self.characters_dir = self.data_dir / 'characters'
        self.settings_dir = self.data_dir / 'settings'
        self.plots_dir = self.data_dir / 'plots'
        self.summary_dir = self.data_dir / 'summaries'
        
        # 设置LLM客户端
        llm_api_key = self.config.get('llm_api_key')
        llm_base_url = self.config.get('llm_base_url', 'https://api.deepseek.com')
        self.client = OpenAI(
            api_key=llm_api_key,
            base_url=llm_base_url
        )
        self.llm_model = self.config.get('llm_model', 'deepseek-chat')
        
    def initialize(self) -> bool:
        """初始化知识提取资源
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 创建必要的目录
            self.characters_dir.mkdir(parents=True, exist_ok=True)
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            self.plots_dir.mkdir(parents=True, exist_ok=True)
            self.summary_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建knowledge目录
            knowledge_dir = self.data_dir / 'knowledge'
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            
            self.is_initialized = True
            logger.info("知识提取代理初始化成功")
            return True
        except Exception as e:
            logger.exception(f"知识提取代理初始化失败: {str(e)}")
            return False
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行知识提取
        
        Args:
            context: 上下文信息，包括：
                - document_info: 文档信息
                - chapters_dir: 章节目录
                
        Returns:
            Dict[str, Any]: 处理结果
        """
        super().execute(context)
        
        document_info = context.get('document_info')
        if not document_info:
            return {
                "status": "error",
                "message": "文档信息不能为空"
            }
            
        document_id = document_info.get('document_id')
        if not document_id:
            return {
                "status": "error",
                "message": "文档ID不能为空"
            }
        
        chapters_dir = context.get('chapters_dir')
        if not chapters_dir:
            # 使用默认章节目录
            chapters_dir = self.data_dir / 'chapters' / document_id
        else:
            chapters_dir = Path(chapters_dir)
            
        if not chapters_dir.exists():
            return {
                "status": "error",
                "message": f"章节目录不存在: {chapters_dir}"
            }
            
        total_chapters = document_info.get('total_chapters', 0)
        if total_chapters <= 0:
            return {
                "status": "error",
                "message": f"无效的章节数量: {total_chapters}"
            }
            
        try:
            # 创建文档特定的子目录
            doc_characters_dir = self.characters_dir / document_id
            doc_settings_dir = self.settings_dir / document_id
            doc_plots_dir = self.plots_dir / document_id
            doc_summary_dir = self.summary_dir / document_id
            
            doc_characters_dir.mkdir(parents=True, exist_ok=True)
            doc_settings_dir.mkdir(parents=True, exist_ok=True)
            doc_plots_dir.mkdir(parents=True, exist_ok=True)
            doc_summary_dir.mkdir(parents=True, exist_ok=True)
            
            # 处理每个章节
            knowledge_base = {
                "characters": {},
                "settings": {},
                "plots": [],
                "chapter_summaries": []
            }
            
            # 先生成整体摘要
            overall_summary = self._generate_overall_summary(document_info, chapters_dir)
            
            # 将整体摘要保存到文件
            with open(doc_summary_dir / "overall_summary.json", "w", encoding="utf-8") as f:
                json.dump(overall_summary, f, ensure_ascii=False, indent=2)
                
            knowledge_base["overall_summary"] = overall_summary
            
            # 分析并提取主要角色
            main_characters = self._extract_main_characters(overall_summary)
            
            # 分析每个章节
            for chapter_num in range(1, total_chapters + 1):
                chapter_file = chapters_dir / f"chapter_{chapter_num:03d}.txt"
                
                if not chapter_file.exists():
                    logger.warning(f"章节文件不存在: {chapter_file}")
                    continue
                    
                logger.info(f"处理章节 {chapter_num}/{total_chapters}")
                
                # 读取章节内容
                with open(chapter_file, "r", encoding="utf-8") as f:
                    chapter_content = f.read()
                    
                # 生成章节摘要
                chapter_summary = self._generate_chapter_summary(chapter_num, chapter_content, main_characters)
                
                # 提取章节知识
                chapter_knowledge = self._extract_chapter_knowledge(chapter_num, chapter_content, chapter_summary, main_characters)
                
                # 将章节摘要保存到文件
                with open(doc_summary_dir / f"summary_{chapter_num:03d}.json", "w", encoding="utf-8") as f:
                    json.dump(chapter_summary, f, ensure_ascii=False, indent=2)
                    
                # 更新知识库
                self._update_knowledge_base(knowledge_base, chapter_knowledge)
                knowledge_base["chapter_summaries"].append(chapter_summary)
                
                # 将章节知识保存到文件
                with open(doc_plots_dir / f"chapter_{chapter_num:03d}_knowledge.json", "w", encoding="utf-8") as f:
                    json.dump(chapter_knowledge, f, ensure_ascii=False, indent=2)
            
            # 生成最终的角色信息
            character_info = self._generate_character_info(knowledge_base)
            with open(doc_characters_dir / "characters.json", "w", encoding="utf-8") as f:
                json.dump(character_info, f, ensure_ascii=False, indent=2)
                
            # 生成最终的设定信息
            setting_info = self._generate_setting_info(knowledge_base)
            with open(doc_settings_dir / "settings.json", "w", encoding="utf-8") as f:
                json.dump(setting_info, f, ensure_ascii=False, indent=2)
                
            # 生成最终的情节信息
            plot_info = self._generate_plot_info(knowledge_base)
            with open(doc_plots_dir / "plots.json", "w", encoding="utf-8") as f:
                json.dump(plot_info, f, ensure_ascii=False, indent=2)
                
            # 将整个知识库保存到文件
            with open(self.data_dir / 'knowledge' / f"{document_id}_knowledge.json", "w", encoding="utf-8") as f:
                json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
                
            return {
                "status": "success",
                "message": "知识提取成功",
                "knowledge_base": {
                    "characters": character_info,
                    "settings": setting_info,
                    "plots": plot_info,
                    "overall_summary": overall_summary,
                    "document_id": document_id
                }
            }
                
        except Exception as e:
            logger.exception(f"知识提取失败: {str(e)}")
            return {
                "status": "error",
                "message": f"知识提取出错: {str(e)}"
            }
    
    def _generate_overall_summary(self, document_info: Dict[str, Any], chapters_dir: Path) -> Dict[str, Any]:
        """生成整体摘要
        
        Args:
            document_info: 文档信息
            chapters_dir: 章节目录
            
        Returns:
            Dict[str, Any]: 整体摘要
        """
        logger.info("生成整体摘要")
        
        # 获取前三章内容作为整体分析的样本
        samples = []
        total_chapters = document_info.get('total_chapters', 0)
        
        # 最多取前三章和最后一章
        sample_chapters = list(range(1, min(4, total_chapters + 1)))
        if total_chapters > 5:
            sample_chapters.append(total_chapters)
            
        for chapter_num in sample_chapters:
            chapter_file = chapters_dir / f"chapter_{chapter_num:03d}.txt"
            
            if chapter_file.exists():
                try:
                    with open(chapter_file, "r", encoding="utf-8") as f:
                        chapter_content = f.read()
                        
                    # 为了控制篇幅，只取章节的前2000个字符和后1000个字符
                    if len(chapter_content) > 3000:
                        chapter_sample = chapter_content[:2000] + "...\n[中间内容省略]...\n" + chapter_content[-1000:]
                    else:
                        chapter_sample = chapter_content
                        
                    samples.append({
                        "chapter_num": chapter_num,
                        "content_sample": chapter_sample
                    })
                except Exception as e:
                    logger.error(f"读取章节文件失败: {chapter_file}, 错误: {str(e)}")
        
        # 构建提示
        title = document_info.get('title', '未知标题')
        language = document_info.get('language', 'zh')
        
        prompt = f"""请基于以下文档信息和章节样本，生成一份详细的整体摘要。

文档信息:
- 标题: {title}
- 语言: {language}
- 总章节数: {total_chapters}

章节样本:
"""

        for sample in samples:
            prompt += f"\n--- 第{sample['chapter_num']}章样本 ---\n{sample['content_sample']}\n"
            
        prompt += """
请提供以下信息:
1. 故事背景设定: 时代背景、世界观等
2. 主要角色列表: 每个角色的简要描述
3. 故事主题: 作品想要表达的主题思想
4. 故事大纲: 整体的故事发展脉络
5. 风格特点: 写作风格、叙述视角等

请以JSON格式返回，包括以下字段:
- background: 故事背景设定
- main_characters: 主要角色列表，每个角色包含name和description字段
- theme: 故事主题
- outline: 故事大纲
- style: 风格特点
"""
        
        # 调用LLM生成整体摘要
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 处理可能的markdown代码块
                if content.startswith('```json') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                elif content.startswith('```') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                    
                return json.loads(content)
            except json.JSONDecodeError:
                logger.warning("LLM返回的内容不是有效的JSON格式，尝试提取JSON部分")
                
                # 尝试查找JSON内容
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, content)
                
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        logger.error("无法解析提取的JSON内容")
                
                # 返回一个基本的结构
                return {
                    "background": "无法自动提取故事背景",
                    "main_characters": [],
                    "theme": "无法自动提取故事主题",
                    "outline": "无法自动提取故事大纲",
                    "style": "无法自动提取风格特点"
                }
                
        except Exception as e:
            logger.exception(f"生成整体摘要失败: {str(e)}")
            return {
                "background": "生成摘要过程中出错",
                "main_characters": [],
                "theme": "生成摘要过程中出错",
                "outline": "生成摘要过程中出错",
                "style": "生成摘要过程中出错"
            }
    
    def _extract_main_characters(self, overall_summary: Dict[str, Any]) -> List[Dict[str, str]]:
        """从整体摘要中提取主要角色
        
        Args:
            overall_summary: 整体摘要
            
        Returns:
            List[Dict[str, str]]: 主要角色列表
        """
        main_characters = overall_summary.get('main_characters', [])
        
        # 确保角色数据结构一致
        standardized_characters = []
        for char in main_characters:
            if isinstance(char, dict):
                if 'name' in char and 'description' in char:
                    standardized_characters.append({
                        'name': char['name'],
                        'description': char['description']
                    })
                elif 'name' in char:
                    standardized_characters.append({
                        'name': char['name'],
                        'description': char.get('description', '未知')
                    })
            elif isinstance(char, str):
                # 尝试从字符串中提取角色名
                if ':' in char:
                    parts = char.split(':', 1)
                    standardized_characters.append({
                        'name': parts[0].strip(),
                        'description': parts[1].strip()
                    })
                else:
                    standardized_characters.append({
                        'name': char,
                        'description': '未知'
                    })
        
        return standardized_characters
    
    def _generate_chapter_summary(self, chapter_num: int, chapter_content: str, main_characters: List[Dict[str, str]]) -> Dict[str, Any]:
        """生成章节摘要
        
        Args:
            chapter_num: 章节编号
            chapter_content: 章节内容
            main_characters: 主要角色列表
            
        Returns:
            Dict[str, Any]: 章节摘要
        """
        logger.info(f"生成第{chapter_num}章摘要")
        
        # 对于长章节，只取前3000字和后1000字进行分析
        if len(chapter_content) > 4000:
            content_to_analyze = chapter_content[:3000] + "\n...\n" + chapter_content[-1000:]
        else:
            content_to_analyze = chapter_content
            
        # 构建角色列表
        character_names = [char['name'] for char in main_characters]
        
        # 构建提示
        prompt = f"""请基于以下章节内容，生成一份详细的章节摘要。

章节编号: {chapter_num}

已知主要角色: {', '.join(character_names)}

章节内容:
{content_to_analyze}

请提供以下信息:
1. 章节摘要: 本章的主要内容概述
2. 出场角色: 本章中出现的角色
3. 关键事件: 本章中发生的重要事件
4. 情节发展: 本章对整体故事的推进作用
5. 环境描写: 本章中出现的场景和环境

请以JSON格式返回，包括以下字段:
- summary: 章节摘要
- characters: 出场角色列表，每个角色包含name和role字段（role表示在本章中的作用）
- key_events: 关键事件列表
- plot_development: 情节发展
- settings: 环境描写列表
- chapter_num: 章节编号
"""
        
        # 调用LLM生成章节摘要
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 处理可能的markdown代码块
                if content.startswith('```json') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                elif content.startswith('```') and content.endswith('```'):
                    content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
                    
                summary = json.loads(content)
                
                # 确保包含章节编号
                summary['chapter_num'] = chapter_num
                
                return summary
            except json.JSONDecodeError:
                logger.warning("LLM返回的内容不是有效的JSON格式，尝试提取JSON部分")
                
                # 尝试查找JSON内容
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, content)
                
                if match:
                    try:
                        summary = json.loads(match.group(0))
                        summary['chapter_num'] = chapter_num
                        return summary
                    except json.JSONDecodeError:
                        logger.error("无法解析提取的JSON内容")
                
                # 返回一个基本的结构
                return {
                    "summary": "无法自动提取章节摘要",
                    "characters": [],
                    "key_events": [],
                    "plot_development": "无法自动提取情节发展",
                    "settings": [],
                    "chapter_num": chapter_num
                }
                
        except Exception as e:
            logger.exception(f"生成章节摘要失败: {str(e)}")
            return {
                "summary": "生成摘要过程中出错",
                "characters": [],
                "key_events": [],
                "plot_development": "生成摘要过程中出错",
                "settings": [],
                "chapter_num": chapter_num
            }
    
    def _extract_chapter_knowledge(self, chapter_num: int, chapter_content: str, chapter_summary: Dict[str, Any], main_characters: List[Dict[str, str]]) -> Dict[str, Any]:
        """提取章节知识
        
        Args:
            chapter_num: 章节编号
            chapter_content: 章节内容
            chapter_summary: 章节摘要
            main_characters: 主要角色列表
            
        Returns:
            Dict[str, Any]: 章节知识
        """
        logger.info(f"提取第{chapter_num}章知识")
        
        # 构建角色列表
        character_info = {char['name']: char['description'] for char in main_characters}
        
        # 从摘要中获取出场角色
        appearing_characters = []
        for char in chapter_summary.get('characters', []):
            if isinstance(char, dict) and 'name' in char:
                name = char['name']
                role = char.get('role', '未知')
                appearing_characters.append({
                    'name': name,
                    'role': role,
                    'description': character_info.get(name, '未知')
                })
            elif isinstance(char, str):
                appearing_characters.append({
                    'name': char,
                    'role': '未知',
                    'description': character_info.get(char, '未知')
                })
                
        # 从摘要中获取环境设定
        settings = chapter_summary.get('settings', [])
        if isinstance(settings, list):
            formatted_settings = settings
        elif isinstance(settings, str):
            formatted_settings = [settings]
        else:
            formatted_settings = []
            
        # 获取关键事件
        key_events = chapter_summary.get('key_events', [])
        if isinstance(key_events, list):
            formatted_events = key_events
        elif isinstance(key_events, str):
            formatted_events = [key_events]
        else:
            formatted_events = []
            
        # 构建章节知识
        chapter_knowledge = {
            "chapter_num": chapter_num,
            "characters": appearing_characters,
            "settings": formatted_settings,
            "events": formatted_events,
            "plot_development": chapter_summary.get('plot_development', ''),
            "summary": chapter_summary.get('summary', '')
        }
        
        return chapter_knowledge
    
    def _update_knowledge_base(self, knowledge_base: Dict[str, Any], chapter_knowledge: Dict[str, Any]) -> None:
        """更新知识库
        
        Args:
            knowledge_base: 知识库
            chapter_knowledge: 章节知识
        """
        # 更新角色信息
        for char in chapter_knowledge.get('characters', []):
            name = char.get('name')
            if not name:
                continue
                
            if name not in knowledge_base["characters"]:
                knowledge_base["characters"][name] = {
                    "description": char.get('description', ''),
                    "appearances": [chapter_knowledge.get('chapter_num')],
                    "roles": [char.get('role', '未知')],
                    "development": []
                }
            else:
                # 更新角色出场信息
                if chapter_knowledge.get('chapter_num') not in knowledge_base["characters"][name]["appearances"]:
                    knowledge_base["characters"][name]["appearances"].append(chapter_knowledge.get('chapter_num'))
                    
                # 更新角色描述（如果原本为空）
                if not knowledge_base["characters"][name]["description"] and char.get('description'):
                    knowledge_base["characters"][name]["description"] = char.get('description')
                    
                # 更新角色在本章的角色
                if char.get('role') and char.get('role') not in knowledge_base["characters"][name]["roles"]:
                    knowledge_base["characters"][name]["roles"].append(char.get('role'))
                    
        # 更新设定信息
        for setting in chapter_knowledge.get('settings', []):
            if isinstance(setting, str):
                setting_name = setting
                setting_description = ""
            elif isinstance(setting, dict):
                setting_name = setting.get('name', '')
                setting_description = setting.get('description', '')
            else:
                continue
                
            if not setting_name:
                continue
                
            if setting_name not in knowledge_base["settings"]:
                knowledge_base["settings"][setting_name] = {
                    "description": setting_description,
                    "appearances": [chapter_knowledge.get('chapter_num')],
                }
            else:
                # 更新设定出场信息
                if chapter_knowledge.get('chapter_num') not in knowledge_base["settings"][setting_name]["appearances"]:
                    knowledge_base["settings"][setting_name]["appearances"].append(chapter_knowledge.get('chapter_num'))
                    
                # 更新设定描述（如果原本为空）
                if not knowledge_base["settings"][setting_name]["description"] and setting_description:
                    knowledge_base["settings"][setting_name]["description"] = setting_description
        
        # 更新情节信息
        for event in chapter_knowledge.get('events', []):
            if isinstance(event, str):
                event_description = event
            elif isinstance(event, dict):
                event_description = event.get('description', '')
            else:
                continue
                
            if not event_description:
                continue
                
            knowledge_base["plots"].append({
                "description": event_description,
                "chapter": chapter_knowledge.get('chapter_num'),
                "importance": 3  # 默认中等重要性
            })
    
    def _generate_character_info(self, knowledge_base: Dict[str, Any]) -> Dict[str, Any]:
        """生成角色信息
        
        Args:
            knowledge_base: 知识库
            
        Returns:
            Dict[str, Any]: 角色信息
        """
        character_info = {}
        
        for name, char in knowledge_base["characters"].items():
            # 根据出场次数排序角色重要性
            appearances = char.get('appearances', [])
            importance = len(appearances)
            
            character_info[name] = {
                "description": char.get('description', ''),
                "appearances": appearances,
                "importance": importance,
                "roles": char.get('roles', []),
                "development": char.get('development', [])
            }
            
        return character_info
    
    def _generate_setting_info(self, knowledge_base: Dict[str, Any]) -> Dict[str, Any]:
        """生成设定信息
        
        Args:
            knowledge_base: 知识库
            
        Returns:
            Dict[str, Any]: 设定信息
        """
        setting_info = {}
        
        for name, setting in knowledge_base["settings"].items():
            # 根据出场次数排序设定重要性
            appearances = setting.get('appearances', [])
            importance = len(appearances)
            
            setting_info[name] = {
                "description": setting.get('description', ''),
                "appearances": appearances,
                "importance": importance
            }
            
        return setting_info
    
    def _generate_plot_info(self, knowledge_base: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成情节信息
        
        Args:
            knowledge_base: 知识库
            
        Returns:
            List[Dict[str, Any]]: 情节信息
        """
        # 按章节排序情节
        return sorted(knowledge_base["plots"], key=lambda x: x.get('chapter', 0))
    
    def get_characters(self, document_id: str) -> Dict[str, Any]:
        """获取文档角色信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 角色信息
        """
        character_file = self.characters_dir / document_id / "characters.json"
        
        if not character_file.exists():
            return {}
            
        try:
            with open(character_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取角色信息失败: {character_file}, 错误: {str(e)}")
            return {}
    
    def get_settings(self, document_id: str) -> Dict[str, Any]:
        """获取文档设定信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 设定信息
        """
        setting_file = self.settings_dir / document_id / "settings.json"
        
        if not setting_file.exists():
            return {}
            
        try:
            with open(setting_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取设定信息失败: {setting_file}, 错误: {str(e)}")
            return {}
    
    def get_plots(self, document_id: str) -> List[Dict[str, Any]]:
        """获取文档情节信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            List[Dict[str, Any]]: 情节信息
        """
        plot_file = self.plots_dir / document_id / "plots.json"
        
        if not plot_file.exists():
            return []
            
        try:
            with open(plot_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取情节信息失败: {plot_file}, 错误: {str(e)}")
            return []
    
    def get_chapter_summary(self, document_id: str, chapter_num: int) -> Dict[str, Any]:
        """获取章节摘要
        
        Args:
            document_id: 文档ID
            chapter_num: 章节编号
            
        Returns:
            Dict[str, Any]: 章节摘要
        """
        summary_file = self.summary_dir / document_id / f"summary_{chapter_num:03d}.json"
        
        if not summary_file.exists():
            return {}
            
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取章节摘要失败: {summary_file}, 错误: {str(e)}")
            return {} 