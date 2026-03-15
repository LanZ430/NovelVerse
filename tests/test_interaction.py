import sys
from pathlib import Path
import logging
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.interaction import CharacterInteraction
from config.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class StoryState:
    """故事状态追踪"""
    current_chapter: int
    current_scene: str
    character_states: Dict[str, Dict] = field(default_factory=dict)
    divergence_points: List[Dict] = field(default_factory=list)
    
    def update(self, chapter: int, scene: str, character_updates: Dict = None):
        self.current_chapter = chapter
        self.current_scene = scene
        if character_updates:
            for char, state in character_updates.items():
                if char not in self.character_states:
                    self.character_states[char] = {}
                self.character_states[char].update(state)

    def add_divergence(self, chapter: int, choice: str, evaluation: Dict):
        """记录故事偏离点，包含LLM的评估结果"""
        self.divergence_points.append({
            'chapter': chapter,
            'choice': choice,
            'evaluation': evaluation,
            'timestamp': time.time()
        })

class InteractionMemory:
    """交互记忆管理"""
    def __init__(self, max_history: int = 10):
        self.short_term = []  # 最近的对话历史
        self.max_history = max_history
        self.story_state = None
    
    def add_interaction(self, role: str, content: str, metadata: Dict = None):
        self.short_term.append({
            'role': role,
            'content': content,
            'metadata': metadata,
            'timestamp': time.time()
        })
        if len(self.short_term) > self.max_history:
            self.short_term.pop(0)
    
    def get_context(self, current_chapter: int, include_history: bool = True) -> List[Dict]:
        """获取当前上下文，包括对话历史和故事状态"""
        context = []
        if include_history:
            context.extend(self.short_term)
        if self.story_state:
            context.append({
                'role': 'system',
                'content': f"当前章节：{current_chapter}\n"
                          f"当前场景：{self.story_state.current_scene}\n"
                          f"角色状态：{json.dumps(self.story_state.character_states, ensure_ascii=False)}"
            })
        return context

class InteractionGuide:
    """基于元数据生成的交互引导系统"""
    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.metadata_dir = Path("D:/ACode/AIFoundationAgent/data/novels") / novel_id / "metadata"
        self.chapters_metadata = []
        self.characters = {}
        self.plot_points = []
        self.memory = InteractionMemory()
        self.story_state = StoryState(current_chapter=1, current_scene="开始")
        self.interaction = CharacterInteraction(novel_id)
        self.load_metadata()

    def load_metadata(self):
        """加载所有章节的元数据"""
        try:
            if not self.metadata_dir.exists():
                raise FileNotFoundError(f"Metadata directory not found: {self.metadata_dir}")
            
            metadata_files = sorted(self.metadata_dir.glob("metadata_*.json"))
            metadata_files_list = list(metadata_files)
            
            if not metadata_files_list:
                raise FileNotFoundError(f"No metadata files found in: {self.metadata_dir}")
            
            for file_path in metadata_files_list:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        self.chapters_metadata.append(metadata)
                        
                        # 收集角色信息
                        for char in metadata.get('characters', []):
                            char_name = char['name']
                            if char_name not in self.characters:
                                self.characters[char_name] = {
                                    'first_appearance': len(self.chapters_metadata),
                                    'description': char.get('description', ''),
                                    'importance': char.get('importance', 0),
                                    'relationships': char.get('relationships', [])
                                }
                        
                        # 收集关键剧情点
                        if 'plot_points' in metadata:
                            self.plot_points.extend([
                                {**point, 'chapter': len(self.chapters_metadata)}
                                for point in metadata['plot_points']
                            ])
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"Error loading metadata: {str(e)}")
            raise

    def get_available_characters(self) -> List[Dict]:
        """获取可选择的角色列表"""
        return [
            {
                'name': name,
                'info': info,
                'type': 'protagonist' if info['importance'] > 8 else 
                       'major_supporting' if info['importance'] > 5 else 
                       'supporting'
            }
            for name, info in self.characters.items()
        ]

    def find_character_first_chapter(self, character_name: str) -> int:
        """查找角色首次出现的章节"""
        for chapter_idx, metadata in enumerate(self.chapters_metadata):
            for char in metadata.get('characters', []):
                if char['name'] == character_name:
                    return chapter_idx
        return 0  # 如果没找到，返回第一章

    def get_background_context(self, start_chapter: int) -> Dict:
        """获取指定章节之前的背景信息"""
        background = {
            'previous_summaries': [],
            'key_events': [],
            'important_characters': set(),
            'locations': set(),
            'items': set()
        }
        
        # 收集之前章节的信息
        for chapter in range(start_chapter):
            # 获取章节摘要
            chapter_num = str(chapter).zfill(3)
            summary_path = Path("D:/ACode/AIFoundationAgent/data/novels") / self.novel_id / "summaries" / f"summary_{chapter_num}.txt"
            try:
                if summary_path.exists():
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        background['previous_summaries'].append({
                            'chapter': chapter + 1,
                            'content': f.read().strip()
                        })
            except Exception as e:
                logger.error(f"Error reading summary file {summary_path}: {str(e)}")

            # 获取元数据中的重要信息
            metadata = self.chapters_metadata[chapter]
            
            # 收集重要事件
            for event in metadata.get('events', []):
                if event.get('importance', 0) >= 4:  # 只收集重要性大于等于4的事件
                    background['key_events'].append({
                        'chapter': chapter + 1,
                        'description': event['description']
                    })
            
            # 收集重要角色
            for char in metadata.get('characters', []):
                background['important_characters'].add(char['name'])
            
            # 收集地点
            for loc in metadata.get('locations', []):
                background['locations'].add(loc['name'])
            
            # 收集重要物品
            for item in metadata.get('items', []):
                background['items'].add(item['name'])
        
        # 转换集合为列表
        background['important_characters'] = list(background['important_characters'])
        background['locations'] = list(background['locations'])
        background['items'] = list(background['items'])
        
        return background

    def evaluate_story_progression(self, chapter: int, character_name: str, story_state: Dict) -> Dict:
        """评估故事进展"""
        try:
            return self.interaction.evaluate_story_progression(
                chapter=chapter,
                character_name=character_name,
                user_choice=story_state.get('previous_responses', [])[-1] if story_state.get('previous_responses') else {}
            )
        except Exception as e:
            logger.error(f"Error evaluating story progression: {str(e)}")
            return {
                "should_proceed_chapter": False,
                "character_consistency": {"is_consistent": True, "violation_points": []},
                "world_consistency": {"is_consistent": True, "violation_points": []},
                "divergence_level": 0,
                "continuation_suggestion": "继续当前情节"
            }

def display_scene(scene: Dict):
    """显示场景信息"""
    try:
        # 显示章节标题
        if scene.get('progress_info', {}).get('current_scene'):
            print(f"\n=== {scene['progress_info']['current_scene']} ===")
        
        # 显示叙述
        if scene.get('narrative'):
            print(f"\n{scene['narrative']}")
        
        # 显示环境描述
        if scene.get('environment'):
            print(f"\n[环境] {scene['environment']}")
        
        # 显示角色状态
        if scene.get('character_state'):
            print(f"\n[状态] {scene['character_state']}")
        
        # 显示其他角色
        if scene.get('other_characters'):
            print("\n[场景中的其他角色]")
            for char in scene['other_characters']:
                print(f"- {char}")
        
        # 显示氛围
        if scene.get('atmosphere'):
            print(f"\n[氛围] {scene['atmosphere']}")
        
        # 显示关键元素
        if scene.get('key_elements'):
            print("\n[关键元素]")
            for element in scene['key_elements']:
                print(f"- {element}")
        
        # 显示互动点
        if scene.get('interaction_points'):
            print("\n[可能的互动]")
            for point in scene['interaction_points']:
                print(f"- {point.get('description', '')}")
        
        # 显示进度信息
        if scene.get('progress_info'):
            progress = scene['progress_info']
            print(f"\n[进度] {progress.get('progress_percentage', 0)}%")
            
            if progress.get('completed_plot_points'):
                print("\n已完成的情节：")
                for point in progress['completed_plot_points']:
                    print(f"- {point}")
                    
            if progress.get('chapter_completion_conditions'):
                print("\n[完成本章需要]")
                for condition in progress['chapter_completion_conditions']:
                    print(f"- {condition}")
                
    except Exception as e:
        logger.error(f"Error displaying scene: {str(e)}")
        print("\n[系统] 显示场景信息时出现问题")

def display_evaluation_result(evaluation: Dict):
    """显示评估结果"""
    try:
        # 显示叙述性回应
        if evaluation.get('narrative_response'):
            print(f"\n{evaluation['narrative_response']}")
        
        # 显示世界观一致性评估
        if evaluation.get('world_consistency') is not None:
            print(f"\n[世界观一致性] {evaluation['world_consistency']}/10")
        
        # 显示角色一致性评估
        if evaluation.get('character_consistency') is not None:
            print(f"\n[角色一致性] {evaluation['character_consistency']}/10")
        
        # 显示偏离程度
        if evaluation.get('divergence_level') is not None:
            print(f"\n[故事偏离程度] {evaluation['divergence_level']}/10")
        
        # 显示关系变化
        if evaluation.get('relationship_changes'):
            print("\n[关系变化]")
            for char, change in evaluation['relationship_changes'].items():
                print(f"- 与{char}的关系: {change}")
        
        # 显示继续建议
        if evaluation.get('next_interaction_hint'):
            print(f"\n[提示] {evaluation['next_interaction_hint']}")
            
    except Exception as e:
        logger.error(f"Error displaying evaluation result: {str(e)}")
        print("\n[系统] 显示评估结果时出现问题")

def get_user_choice(options: List[str], prompt: str) -> int:
    """获取用户选择"""
    while True:
        print(f"\n{prompt}")
        for i, option in enumerate(options, 1):
            print(f"{i}. {option}")
        try:
            choice = input("\n请输入你的选择 (输入数字): ")
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                return choice_num - 1
            print("无效的选择，请重试。")
        except ValueError:
            print("请输入有效的数字。")

def get_user_input(prompt: str) -> str:
    """获取用户输入"""
    return input(f"\n{prompt}: ").strip()

def get_user_confirmation(prompt: str) -> bool:
    """获取用户确认"""
    while True:
        response = input(f"\n{prompt} (y/n): ").lower().strip()
        if response in ['y', 'n']:
            return response == 'y'
        print("请输入 y 或 n")

def initialize_story(novel_id: str) -> Tuple[InteractionGuide, Dict, Dict]:
    """初始化故事系统"""
    try:
        guide = InteractionGuide(novel_id)
        # 确保知识库初始化
        guide.interaction.initialize_knowledge_base()
        
        print("\n=== 欢迎来到《小王子》的互动世界 ===")
        print("\n在这个世界里，你将跟随故事发展，在关键时刻做出你的选择。")
        
        # 角色选择
        available_chars = guide.get_available_characters()
        char_options = [f"{char['name']} - {char['info']['description']}" for char in available_chars]
        char_idx = get_user_choice(char_options, "请选择你想要扮演的角色：")
        character = available_chars[char_idx]
        
        print(f"\n你选择了 {character['name']}")
        print("正在进入故事世界...")
        time.sleep(1)
        
        # 初始化故事状态
        start_chapter = guide.find_character_first_chapter(character['name'])
        
        # 预加载选定角色所在章节的原文内容和元数据
        _ = guide.interaction._get_chapter_content(start_chapter)
        
        story_state = {
            'current_chapter': start_chapter,
            'previous_responses': [],
            'character_state': {},
            'story_progress': start_chapter
        }
        
        # 获取精简的角色背景信息
        background_info = guide.interaction._get_condensed_background(start_chapter) if start_chapter > 0 else ""
        
        if background_info:
            print("\n=== 故事背景 ===")
            print(background_info)
            print("\n现在，让我们从你的角色登场开始...")
            time.sleep(2)
        
        return guide, character, story_state
        
    except Exception as e:
        logger.error(f"Error initializing story: {str(e)}")
        raise

def run_story_interaction(guide: InteractionGuide, character: Dict, story_state: Dict):
    """运行故事交互"""
    try:
        chapter_complete = False
        
        while True:
            # 生成场景
            scene = guide.interaction.generate_scene(
                chapter=story_state['current_chapter'],
                character_name=character['name'],
                story_state=story_state,
                is_immersive=True
            )
            
            if not scene:
                print("\n[系统] 生成场景时出现问题，请稍后再试。")
                return
            
            # 保存交互ID以跟踪交互连续性
            interaction_id = scene.get('interaction_id', '')
            if interaction_id:
                story_state['last_interaction_id'] = interaction_id
            
            # 显示场景
            display_scene(scene)
            
            # 获取用户回应
            response = get_user_input("你的回应")
            if not response:
                print("\n[提示] 请输入有效的回应。")
                continue
            
            # 评估回应
            try:
                evaluation = guide.interaction.evaluate_story_response(
                    response=response,
                    current_chapter=story_state['current_chapter'],
                    character_name=character['name'],
                    story_state=story_state,
                    current_scene=scene
                )
                
                if not evaluation:
                    print("\n[系统] 评估回应时出现问题，请重试。")
                    continue
                
                # 显示评估结果
                display_evaluation_result(evaluation)
                
                # 更新故事状态
                story_state['previous_responses'].append({
                    'response': response,
                    'evaluation': evaluation,
                    'interaction_id': interaction_id
                })
                
                # 记录交互历史
                guide.interaction.interaction_state.add_interaction_history(
                    story_state['current_chapter'], 
                    {
                        'interaction_id': interaction_id,
                        'narrative': scene.get('narrative', ''),
                        'user_response': response,
                        'evaluation': evaluation
                    }
                )
                
                # 检查是否完成当前章节
                if chapter_complete or scene.get('progress_info', {}).get('can_proceed_to_next', False):
                    print("\n[系统] 你已经完成了这一章的主要情节。")
                    if get_user_confirmation("是否继续下一章？"):
                        story_state['current_chapter'] += 1
                        print(f"\n正在进入第 {story_state['current_chapter'] + 1} 章...")
                        # 重置章节完成状态
                        chapter_complete = False
                        story_state['last_interaction_id'] = None
                        time.sleep(1)
                    else:
                        print("\n让我们继续探索当前的情节...")
                
                # 检查是否到达故事结束
                if story_state['current_chapter'] >= len(guide.chapters_metadata):
                    print("\n=== 故事结束 ===")
                    print("感谢你的体验！")
                    return
                
                # 检查是否需要继续当前章节的下一个交互点
                if evaluation.get('should_progress', False):
                    chapter_complete = True
                
                # 是否继续
                if not get_user_confirmation("要继续吗？"):
                    print("\n感谢你的体验！")
                    return
                    
            except Exception as e:
                logger.error(f"Error evaluating response: {str(e)}")
                print("\n[系统] 处理回应时出现问题，请重试。")
                continue
                
    except Exception as e:
        logger.error(f"Error in story interaction: {str(e)}")
        print("\n[系统] 发生错误，请稍后重试。")

def test_character_interaction():
    """测试角色互动系统"""
    try:
        # 初始化故事
        guide, character, story_state = initialize_story("temp_sample_xiaowangzi")
        
        # 运行故事交互
        run_story_interaction(guide, character, story_state)
        
    except Exception as e:
        logger.error(f"Error in character interaction test: {str(e)}")
        raise

if __name__ == "__main__":
    test_character_interaction() 