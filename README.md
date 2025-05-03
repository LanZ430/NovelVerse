# NovelVerse
Building a Multi-Modal AI Agent for Immersive Fictional Interaction

这是一个基于代理（Agent）架构的沉浸式小说交互系统，允许用户上传小说文本，并通过选择不同角色在故事中进行交互体验。系统使用大型语言模型（LLM）生成沉浸式的交互内容，并支持文生图功能，让故事更加生动。

## 系统特性

- **文档处理**：上传小说文本，自动分章节处理
- **知识提取**：提取角色、设定、情节等信息
- **角色扮演**：选择任一角色进行第一人称体验
- **多交互点**：每章提供多个高自由度交互点
- **故事偏离评估**：智能评估用户选择的故事偏离度
- **文生图能力**：基于场景描述生成图像
- **进度控制**：可跳转章节、调整进度
- **Web界面**：友好的用户交互界面
- **命令行支持**：支持命令行方式运行

## 系统架构

系统采用代理（Agent）架构设计，主要包含以下组件：

- **AgentCoordinator**：代理协调器，管理和协调各个代理
- **DocumentAgent**：文档处理代理，负责解析和预处理文档
- **KnowledgeAgent**：知识提取代理，提取文档中的角色、设定和情节
- **InteractionAgent**：交互代理，处理用户与故事的交互
- **ImageService**：图像服务，提供文生图功能

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

### Web UI 模式

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

## 示例

以《小王子》为例：

1. 上传《小王子》文本
2. 系统提取出"小王子"、"飞行员"、"玫瑰"等角色
3. 选择"小王子"角色体验
4. 系统生成第一人称视角的初始场景
5. 输入你的选择，如"我想去探索新的星球"
6. 系统生成新的场景和交互点
7. 可选择生成当前场景的图像

## 高级功能

- **故事偏离处理**：当用户选择可能导致故事严重偏离时，系统会给出警告
- **第一人称修正**：确保所有内容都从所选角色的第一人称视角生成
- **智能进度评估**：自动评估用户选择对故事进度的影响
- **多风格图像生成**：支持多种图像风格，如写实、动漫、绘画等

## 文生图功能

本系统集成了文生图功能，可以基于场景描述生成与故事相符的图像。

### 使用方法

1. 在交互界面，点击"生成场景图像"按钮
2. 选择您喜欢的图像风格（写实风格、动漫风格、绘画风格、素描风格或3D渲染）
3. 选择合适的图像尺寸（如512x512、512x384等）
4. 点击"生成"按钮，系统将基于当前场景生成图像

### 技术实现

- 使用即梦文生图API（jimeng_high_aes_general_v21_L）
- 按照【艺术风格】+【主体描述】+【文字排版】的模板格式化提示词
- 自动从场景描述中提取关键内容作为提示词
- 利用API的提示词扩写功能（use_pre_llm）优化生成效果
- 支持多种艺术风格和不同尺寸比例

### 即梦API优势

- 强大的文字生成能力：支持准确渲染中文汉字和英文字母
- 优秀的构图能力：画面层次感增强，视角变化多样
- 自然的光影效果：画面表现更加真实自然
- 统一的色彩表现：画面色调统一性增强
- 细腻的质感表现：人物、动物及材质类纹理表现更加真实细腻
- 合理的细节丰富度：画面整体表现更加具有层次感和秩序感

### 待开发功能

以下功能计划在未来版本中实现：

- **负面提示词（Negative Prompt）**：支持指定不希望在图像中出现的内容
- **自定义提示词**：允许用户手动编辑和优化提示词
- **图像批量生成**：一次生成多个不同风格的图像供选择
- **图像局部重绘**：支持对图像的特定区域进行重新生成
- **图像风格一致性**：确保为同一故事生成的多张图像保持风格一致性
- **角色外观一致性**：确保同一角色在不同场景中的外观特征保持一致

## 技术实现

- 使用 DeepSeek Chat API 进行文本内容生成
- 使用 Stability.ai API 进行图像生成
- 使用 Streamlit 构建Web界面
- 采用代理架构实现系统的可扩展性和模块化 