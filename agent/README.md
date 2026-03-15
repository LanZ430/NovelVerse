# 沉浸式小说交互代理系统 (Immersive Novel Interaction Agent System)

这是一个基于代理（Agent）架构的沉浸式小说交互系统，允许用户上传小说文本，并通过选择不同角色在故事中进行第一人称的交互体验。系统使用大型语言模型（LLM）生成沉浸式的交互内容，并支持文生图功能，让故事更加生动。

## 系统特性

- **文档处理**：上传小说文本，自动分章节处理和识别章节模式
- **知识提取**：使用LLM从文本中提取角色、设定、情节等关键信息
- **角色扮演**：选择任一角色进行第一人称视角的沉浸式体验
- **多交互点**：每章提供多个高自由度交互点，用户可自由选择故事发展方向
- **故事偏离评估**：智能评估用户选择的故事偏离度，提供分支结局
- **文生图能力**：基于场景描述生成匹配的画面，支持多种艺术风格
- **进度控制**：可跳转章节、调整进度、保存交互状态
- **记忆系统**：智能提取和管理跨章节的重要记忆，增强叙事连贯性
- **Web界面**：用Streamlit构建的友好用户交互界面
- **命令行支持**：同时支持命令行方式运行

## 系统架构

系统采用代理（Agent）架构设计，主要包含以下组件：

- **AgentCoordinator**：代理协调器，负责初始化和协调各个专业代理的工作
- **DocumentAgent**：文档处理代理，负责解析文本、分章节和生成元数据
- **KnowledgeAgent**：知识提取代理，负责提取文档中的角色、设定和情节信息
- **InteractionAgent**：交互代理，处理用户与故事的交互，生成场景和评估用户输入
- **ImageService**：图像服务，提供基于场景的文生图功能

### 详细架构流程

![系统架构](https://i.imgur.com/qJLkd3F.jpg)

1. **文档处理阶段**：
   - 用户上传小说文本
   - DocumentAgent解析文本，自动检测章节模式
   - 将文本分割成章节并保存
   - 生成文档元数据和小说元数据摘要

2. **知识提取阶段**：
   - KnowledgeAgent分析文本内容
   - 提取主要角色、设定、情节和主题
   - 为每个章节生成摘要
   - 构建角色关系网络和世界观

3. **交互阶段**：
   - 用户选择一个角色进行体验
   - InteractionAgent生成第一人称视角的场景
   - 用户输入选择，系统评估并生成新场景
   - 智能跟踪故事进度和记忆重要事件

## 核心代码组件

### 1. DocumentAgent (document_agent.py)

负责文档处理和章节划分，主要功能包括：

- 上传和解析不同格式的文本文件
- 自动检测章节模式并分章处理
- 生成文档元数据（标题、章节数、语言等）
- 使用LLM创建小说世界观和设定摘要
- 管理所有已处理的文档集合

关键方法：
- `_split_into_chapters`: 基于检测到的模式分割文本
- `_detect_chapter_pattern`: 使用正则表达式自动检测章节标记模式
- `generate_novel_metadata_summary`: 使用LLM生成小说的整体元数据摘要

### 2. KnowledgeAgent (knowledge_agent.py)

负责分析文本并提取结构化知识，功能包括：

- 生成小说整体摘要和主题
- 提取主要角色信息和重要度评估
- 收集世界设定和环境描述
- 跟踪每章的关键事件和情节发展
- 构建章节摘要以支持交互体验

关键方法：
- `_generate_overall_summary`: 生成小说的整体摘要
- `_extract_main_characters`: 提取主要角色列表
- `_generate_chapter_summary`: 为每章生成摘要
- `_extract_chapter_knowledge`: 提取各章节的知识点

### 3. InteractionAgent (interaction_agent.py)

核心交互引擎，负责生成沉浸式体验：

- 基于角色视角生成第一人称叙述
- 评估用户选择并生成相应的场景变化
- 管理长期记忆和情节发展
- 控制故事偏离度和分支结局
- 与文生图服务集成

关键方法：
- `_generate_scene`: 生成沉浸式场景描述
- `_evaluate_user_input`: 评估用户选择对情节的影响
- `_continue_with_deviation`: 处理用户选择继续偏离主线的情况
- `_get_related_memories`: 检索与当前场景相关的记忆
- `_validate_first_person_perspective`: 确保生成内容保持第一人称视角

### 4. Web UI (app.py)

Streamlit构建的用户界面：

- 提供直观的文档上传和处理功能
- 角色选择界面展示角色列表和描述
- 交互界面呈现场景描述和用户选项
- 支持故事搜索和图像生成控制
- 可视化显示情感状态和进度

主要功能区域：
- API设置页：配置LLM和图像生成API密钥
- 上传文档页：上传和处理小说文本
- 角色选择页：选择要扮演的角色
- 交互页面：进行沉浸式故事体验

### 5. Main Entry (main.py)

系统入口点，提供命令行和UI启动功能：

- 处理命令行参数（UI模式、文档处理、知识提取、交互等）
- 配置和初始化代理系统
- 协调各代理之间的工作流程
- 提供命令行交互模式

## 安装

### 前提条件

- Python 3.8+
- DeepSeek API 密钥（用于LLM）
- 即梦API密钥（用于文生图）
  - Access Key ID
  - Secret Access Key

### 安装步骤

1. 克隆或下载本仓库

2. 安装依赖项：

```bash
pip install -r requirements.txt
```

3. 设置环境变量：

```bash
# Linux/Mac
export DEEPSEEK_API_KEY=your_api_key
export IMAGE_ACCESS_KEY_ID=your_access_key_id
export IMAGE_SECRET_KEY=your_secret_access_key

# Windows
set DEEPSEEK_API_KEY=your_api_key
set IMAGE_ACCESS_KEY_ID=your_access_key_id
set IMAGE_SECRET_KEY=your_secret_access_key
```

## 使用方法

### Web UI 模式 (推荐)

启动Web UI：

```bash
python -m agent.main ui
```

然后在浏览器中访问：http://localhost:8501

### 命令行模式

1. 处理文档：

```bash
python -m agent.main process --file path/to/novel.txt --language zh --percentage 100
```

2. 提取知识：

```bash
python -m agent.main knowledge --document document_id
```

3. 开始交互：

```bash
python -m agent.main interact --document document_id --character character_name
```

## Web UI 使用流程

1. **设置 API**：在"API设置"页面配置必要的API密钥
2. **上传文档**：上传文本文件，选择语言和处理百分比
3. **选择角色**：从提取出的角色列表中选择一个进行体验
4. **开始交互**：在交互界面输入你的选择，与故事进行互动
5. **生成图像**：点击"生成场景图像"按钮，创建当前场景的图像
6. **控制进度**：使用界面上的控制按钮跳转章节或停止交互

## 高级功能

- **故事偏离处理**：当用户选择导致故事大幅偏离时，系统将提供警告并可生成替代结局
- **第一人称修正**：自动确保所有内容都从所选角色的第一人称视角生成
- **智能记忆检索**：根据当前场景智能检索相关的过往记忆和线索
- **多风格图像生成**：支持多种图像风格（写实、动漫、绘画、素描、3D等）和尺寸

## 文生图功能

系统集成了文生图功能，可以基于场景描述生成与故事相符的图像。

### 使用方法

1. 在交互界面，点击"生成场景图像"按钮
2. 选择您喜欢的图像风格（写实风格、动漫风格、绘画风格、素描风格或3D渲染）
3. 选择合适的图像尺寸（如512x512、768x768等）
4. 点击"生成"按钮，系统将基于当前场景生成图像

### 技术实现

- 使用即梦文生图API（jimeng_high_aes_general_v21_L）
- 基于场景叙述、关键元素和情感状态构建提示词
- 自动根据场景内容智能选择最合适的图像风格
- 图像尺寸和风格可由用户自定义

## 开发计划

未来版本计划添加的功能：

- **多角色协同互动**：支持在同一故事中切换多个角色视角
- **可视化角色关系图**：展示小说中的角色关系网络
- **用户自定义故事分支**：允许用户创建和分享自定义故事线
- **语音朗读**：支持场景描述的语音朗读功能
- **情感音乐匹配**：根据场景情感自动匹配背景音乐
- **多语言支持扩展**：扩展支持更多语言的小说处理

## 技术实现

- 使用 DeepSeek Chat API 进行文本内容生成
- 使用 即梦 API 进行图像生成
- 使用 Streamlit 构建Web界面
- 采用代理架构实现系统的可扩展性和模块化

## 贡献指南

欢迎对本项目做出贡献！请参考以下步骤：

1. Fork本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 将您的更改推送到分支 (`git push origin feature/amazing-feature`)
5. 开启一个Pull Request

## 许可证

[MIT License](LICENSE) 