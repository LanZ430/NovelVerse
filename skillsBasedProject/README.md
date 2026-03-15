# Skills-Based Project

基于 Agent Skill 架构的沉浸式小说交互系统实现。本项目独立于主项目（AIFoundationAgent），按照 [DESIGN_SKILL_BASED_ARCHITECTURE.md](../DESIGN_SKILL_BASED_ARCHITECTURE.md) 设计方案实现，不污染现有代码。

## 架构概览

- **开发时 Skill**：`.cursor/skills/` 下的 SKILL.md，指导 AI Agent 开发
- **运行时 Skill**：`agent/skills/` 下的 Python 模块，可加载的能力模块
- **Skill 编排器**：`SkillOrchestrator` 协调各 Skill 的加载与调用

## 目录结构

```
skillsBasedProject/
├── .cursor/skills/          # Cursor Agent Skills
│   ├── novel-metadata/
│   ├── storyline-control/
│   ├── image-generation/
│   ├── memory-architecture/
│   └── voice-generation/
├── agent/skills/            # 运行时 Skill 实现
│   ├── registry.py
│   ├── orchestrator.py
│   ├── novel_metadata/
│   ├── storyline_control/
│   ├── image_generation/
│   ├── memory/
│   └── voice/
├── data/books/              # Book Skill 包
└── tests/
```

## 安装与运行

```bash
cd skillsBasedProject
pip install -r requirements.txt
python -m agent.main ui  # 启动 Web UI
```

## 环境变量

- `DEEPSEEK_API_KEY`: LLM API 密钥
- `IMAGE_ACCESS_KEY_ID` / `IMAGE_SECRET_KEY`: 图像生成 API
- `VOICE_APP_ID` / `VOICE_TOKEN`: 语音合成 API
