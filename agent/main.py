import os
import sys
import logging
from pathlib import Path
import argparse

# 添加当前目录到路径
current_dir = Path(__file__).parent
sys.path.append(str(current_dir.parent))

def setup_logging(log_level=logging.INFO):
    """设置日志"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def run_ui():
    """运行Web UI"""
    try:
        # 尝试导入streamlit
        import streamlit
        
        # 执行streamlit命令
        os.system(f"streamlit run {current_dir}/ui/app.py")
    except ImportError:
        print("错误: 未安装streamlit。请使用 'pip install streamlit' 安装。")
        sys.exit(1)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='沉浸式小说体验系统')
    
    # 添加子命令
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # UI命令
    ui_parser = subparsers.add_parser('ui', help='启动Web UI')
    
    # 处理文档命令
    process_parser = subparsers.add_parser('process', help='处理文档')
    process_parser.add_argument('--file', '-f', required=True, help='文档文件路径')
    process_parser.add_argument('--language', '-l', default='zh', choices=['zh', 'en'], help='文档语言')
    process_parser.add_argument('--percentage', '-p', type=int, default=100, help='处理文档百分比')
    
    # 知识提取命令
    knowledge_parser = subparsers.add_parser('knowledge', help='提取知识')
    knowledge_parser.add_argument('--document', '-d', required=True, help='文档ID')
    
    # 交互命令
    interact_parser = subparsers.add_parser('interact', help='开始交互')
    interact_parser.add_argument('--document', '-d', required=True, help='文档ID')
    interact_parser.add_argument('--character', '-c', required=True, help='角色名称')
    interact_parser.add_argument('--chapter', '-ch', type=int, default=1, help='章节编号')
    
    # 日志级别
    parser.add_argument('--verbose', '-v', action='count', default=0, help='增加输出详细程度')
    
    return parser.parse_args()

def process_document(args):
    """处理文档"""
    from agent.core.agent_coordinator import AgentCoordinator
    from agent.core.document_agent import DocumentAgent
    
    # 配置协调器
    coordinator = AgentCoordinator()
    
    # 获取API密钥
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        print("错误: 未设置DEEPSEEK_API_KEY环境变量。")
        sys.exit(1)
        
    # 配置参数
    config = {
        'data_dir': './data',
        'llm_api_key': api_key,
        'supported_languages': ['zh', 'en']
    }
    
    # 注册文档处理代理
    document_agent = DocumentAgent(config)
    coordinator.register_agent('document', document_agent)
    
    # 初始化代理
    coordinator.initialize_all_agents()
    
    # 处理文档
    context = {
        'file_path': args.file,
        'language': args.language,
        'content_percentage': args.percentage
    }
    
    result = coordinator.execute_agent('document', context)
    
    if result.get('status') == 'success':
        document_id = result.get('document_info', {}).get('document_id')
        print(f"文档处理成功: {document_id}")
        print("现在你可以使用以下命令提取知识:")
        print(f"  python -m agent.main knowledge --document {document_id}")
    else:
        print(f"文档处理失败: {result.get('message')}")

def extract_knowledge(args):
    """提取知识"""
    from agent.core.agent_coordinator import AgentCoordinator
    from agent.core.knowledge_agent import KnowledgeAgent
    
    # 配置协调器
    coordinator = AgentCoordinator()
    
    # 获取API密钥
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        print("错误: 未设置DEEPSEEK_API_KEY环境变量。")
        sys.exit(1)
        
    # 配置参数
    config = {
        'data_dir': './data',
        'llm_api_key': api_key
    }
    
    # 注册知识提取代理
    knowledge_agent = KnowledgeAgent(config)
    coordinator.register_agent('knowledge', knowledge_agent)
    
    # 初始化代理
    coordinator.initialize_all_agents()
    
    # 加载文档信息
    document_id = args.document
    metadata_file = Path('./data/metadata') / document_id / "document_info.json"
    
    if not metadata_file.exists():
        print(f"错误: 找不到文档信息: {metadata_file}")
        sys.exit(1)
        
    with open(metadata_file, 'r', encoding='utf-8') as f:
        import json
        document_info = json.load(f)
    
    # 提取知识
    context = {
        'document_info': document_info
    }
    
    result = coordinator.execute_agent('knowledge', context)
    
    if result.get('status') == 'success':
        print("知识提取成功")
        print("现在你可以使用以下命令开始交互:")
        print(f"  python -m agent.main interact --document {document_id} --character <角色名称>")
    else:
        print(f"知识提取失败: {result.get('message')}")

def interact(args):
    """开始交互"""
    from agent.core.agent_coordinator import AgentCoordinator
    from agent.core.interaction import InteractionAgent
    
    # 配置协调器
    coordinator = AgentCoordinator()
    
    # 获取API密钥
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        print("错误: 未设置DEEPSEEK_API_KEY环境变量。")
        sys.exit(1)
        
    # 配置参数
    config = {
        'data_dir': './data',
        'llm_api_key': api_key
    }
    
    # 注册交互代理
    interaction_agent = InteractionAgent(config)
    coordinator.register_agent('interaction', interaction_agent)
    
    # 初始化代理
    coordinator.initialize_all_agents()
    
    # 加载知识库
    document_id = args.document
    
    # 从文件加载知识库
    knowledge_base = {}
    
    # 加载角色信息
    character_file = Path('./data/characters') / document_id / "characters.json"
    if character_file.exists():
        with open(character_file, 'r', encoding='utf-8') as f:
            import json
            knowledge_base['characters'] = json.load(f)
    
    # 开始交互
    context = {
        'action': 'start',
        'document_id': document_id,
        'character_name': args.character,
        'chapter': args.chapter,
        'knowledge_base': knowledge_base
    }
    
    result = coordinator.execute_agent('interaction', context)
    
    if result.get('status') == 'success':
        print(f"已开始与角色 {args.character} 的交互")
        scene = result.get('scene', {})
        
        # 显示场景
        print("\n" + "="*50)
        print("场景描述:")
        print(scene.get('narrative', ''))
        print("\n交互点:")
        print(scene.get('interaction_point', ''))
        print("="*50 + "\n")
        
        # 开始交互循环
        while True:
            user_input = input("你的选择是 (输入'退出'结束交互): ")
            
            if user_input.lower() in ['退出', 'exit', 'quit']:
                break
                
            # 如果检测到故事偏离，提醒用户并询问是否继续
            if result.get('status') == 'warning':
                divergence = result.get('divergence', {})
                print(f"\n警告: 你的选择将导致故事严重偏离原著！偏离度: {divergence.get('level')}/5")
                print(f"偏离描述: {divergence.get('description')}")
                print("如果继续，可能导致故事进入一个全新的分支，与原著相差较大。")
                
                # 询问是否继续
                user_confirm = input("是否仍然继续? (是/否): ")
                
                if user_confirm.lower() not in ['是', 'y', 'yes']:
                    continue
                
                # 用户选择继续偏离的故事，调用continue接口并传递force_continue参数
                result = coordinator.execute_agent('interaction', {
                    'action': 'continue',
                    'user_input': user_input,
                    'force_continue': True
                })
            else:
                # 正常情况下的交互
                context = {
                    'action': 'continue',
                    'user_input': user_input
                }
                
                result = coordinator.execute_agent('interaction', context)
            
            if result.get('status') == 'success':
                # 显示新场景
                scene = result.get('scene', {})
                print("\n" + "="*50)
                print("场景描述:")
                print(scene.get('narrative', ''))
                print("\n交互点:")
                print(scene.get('interaction_point', ''))
                print("="*50 + "\n")
                
                # 检查是否应该进入下一章
                if result.get('should_proceed_chapter'):
                    print("已达到章节结尾，可以进入下一章")
                    
                    next_choice = input("是否进入下一章? (y/n): ")
                    
                    if next_choice.lower() == 'y':
                        # 进入下一章
                        next_context = {
                            'action': 'next_chapter'
                        }
                        
                        next_result = coordinator.execute_agent('interaction', next_context)
                        
                        if next_result.get('status') == 'success':
                            # 显示新章节场景
                            scene = next_result.get('scene', {})
                            print("\n" + "="*50)
                            print(f"已进入第{args.chapter + 1}章")
                            print("场景描述:")
                            print(scene.get('narrative', ''))
                            print("\n交互点:")
                            print(scene.get('interaction_point', ''))
                            print("="*50 + "\n")
                        else:
                            print(f"进入下一章失败: {next_result.get('message')}")
            else:
                print(f"处理选择失败: {result.get('message')}")
                
        # 停止交互
        coordinator.execute_agent('interaction', {'action': 'stop'})
        print("交互已结束")
    else:
        print(f"开始交互失败: {result.get('message')}")

def main():
    """主函数"""
    args = parse_args()
    
    # 设置日志级别
    log_level = logging.WARNING
    if args.verbose >= 2:
        log_level = logging.DEBUG
    elif args.verbose == 1:
        log_level = logging.INFO
        
    setup_logging(log_level)
    
    # 执行命令
    if args.command == 'ui':
        run_ui()
    elif args.command == 'process':
        process_document(args)
    elif args.command == 'knowledge':
        extract_knowledge(args)
    elif args.command == 'interact':
        interact(args)
    else:
        print("请指定命令: ui, process, knowledge 或 interact")
        print("使用 --help 查看帮助")

if __name__ == "__main__":
    main() 