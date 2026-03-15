# 方案2：基于 Agent Skill 的架构设计

## 一、可行性评估

### 1.1 Agent Skill 的本质

根据 Cursor Skill 规范，Skill 具有以下特性：
- **教学性质**：Skill 是 Markdown 文件，用于指导 AI Agent 如何执行特定任务
- **触发机制**：通过 `description` 中的关键词决定何时被加载
- **可组合性**：多个 Skill 可同时生效，形成知识组合
- **项目/个人作用域**：可放在 `.cursor/skills/`（项目级）或 `~/.cursor/skills/`（个人级）

### 1.2 可行性分析

| 维度 | 可行性 | 说明 |
|------|--------|------|
| **元数据 Skill** | ✅ 高 | 每本书的元数据可封装为 Skill 包，Agent 开发/调试时能理解数据结构与约束 |
| **故事线控制 Skill** | ✅ 高 | 作为独立 Skill，指导 Agent 如何实现偏离度评估与引导逻辑 |
| **图像生成 Skill** | ✅ 高 | 指导 Agent 如何构建视觉描述、优化提示词 |
| **记忆架构 Skill** | ✅ 高 | 指导 Agent 理解分层记忆、检索策略、向量化逻辑 |
| **语音生成 Skill** | ✅ 高 | 指导 Agent 排查 Token、音色、对话提取等问题 |
| **Skill 间关系** | ✅ 可行 | 通过 `requires`、`provides`、`references` 等元数据声明依赖与协作 |

### 1.3 双层 Skill 架构

本方案采用**双层 Skill 架构**：

1. **开发时 Skill（Cursor Agent Skills）**  
   供 AI Agent 在开发、调试、重构时使用，以 `.cursor/skills/` 下的 SKILL.md 形式存在。

2. **运行时 Skill（Runtime Skill Modules）**  
   供应用在运行时加载的能力模块，以 Python 包 + 统一接口的形式存在，与开发时 Skill 一一对应。

两者通过**相同的概念模型和术语**保持对齐，便于 Agent 理解运行时行为。

---

## 二、Skill 体系设计

### 2.1 总体架构图

```
                    ┌─────────────────────────────────────────┐
                    │         Skill Orchestrator               │
                    │  (协调各 Skill 的加载、调用与关系)          │
                    └─────────────────────────────────────────┘
                                        │
        ┌───────────────┬───────────────┼───────────────┬───────────────┐
        │               │               │               │               │
        ▼               ▼               ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ NovelMetadata │ │ Storyline     │ │ ImageGen      │ │ Memory        │ │ Voice         │
│ Skill         │ │ Control Skill │ │ Skill         │ │ Architecture  │ │ Generation    │
│               │ │               │ │               │ │ Skill         │ │ Skill        │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │                 │                 │
        │  requires       │  requires       │  requires       │  provides       │  provides
        │  (提供上下文)    │  (提供约束)     │  (提供场景)     │  (提供记忆)     │  (提供音频)
        │                 │                 │                 │                 │
        └─────────────────┴─────────────────┴─────────────────┴─────────────────┴─────────
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │   InteractionAgent    │
                            │   (消费各 Skill 输出)   │
                            └───────────────────────┘
```

### 2.2 Skill 关系矩阵

| 调用方 | 被调用方 | 关系类型 | 说明 |
|--------|----------|----------|------|
| StorylineControl | NovelMetadata | requires | 需要角色、情节锚点、世界观约束 |
| SceneGenerator | NovelMetadata | requires | 需要角色信息、章节摘要、设定 |
| ImageGen | NovelMetadata | requires | 需要角色外观、场景设定 |
| ImageGen | SceneGenerator | consumes | 消费场景的 narrative、key_elements |
| Memory | SceneGenerator | consumes | 消费 memory_update、progress_info |
| Memory | StorylineControl | provides | 提供相关记忆用于偏离评估 |
| Voice | NovelMetadata | requires | 需要角色音色映射 |
| Voice | SceneGenerator | consumes | 消费 narrative 中的对话 |
| InputEvaluator | StorylineControl | uses | 使用偏离度评估逻辑 |
| InputEvaluator | Memory | requires | 需要相关记忆辅助评估 |

---

## 三、各 Skill 详细设计

### 3.1 NovelMetadata Skill（元数据 Skill）

#### 3.1.1 定位
- **开发时**：指导 Agent 如何理解、扩展、校验小说元数据结构
- **运行时**：提供角色、设定、情节等上下文，供其他 Skill 消费

#### 3.1.2 子 Skill 结构

```
novel-metadata/
├── SKILL.md                 # 主 Skill：元数据整体概念与使用方式
├── sub-skills/
│   ├── character-metadata/   # 子 Skill：角色元数据
│   │   └── SKILL.md
│   ├── plot-metadata/       # 子 Skill：情节元数据
│   │   └── SKILL.md
│   ├── scene-metadata/      # 子 Skill：场景/世界观设定
│   │   └── SKILL.md
│   └── continuity-rules/    # 子 Skill：连续性规则
│       └── SKILL.md
├── schemas/
│   ├── character_schema.json
│   ├── plot_schema.json
│   └── setting_schema.json
└── reference.md
```

#### 3.1.3 每本书的元数据作为「Book Skill」

每本书处理完成后，生成一个可加载的 Book Skill 包：

```
data/books/zh-xiaowangzi_1/
├── SKILL.md              # 本书元数据入口，描述本书基本信息
├── characters.json       # 角色数据
├── plots.json           # 情节数据
├── settings.json        # 设定数据
├── world_metadata.json   # 世界观
└── continuity_rules.json # 本书特定的连续性规则
```

#### 3.1.4 Cursor Agent Skill 示例

**`.cursor/skills/novel-metadata/SKILL.md`**

```markdown
---
name: novel-metadata
description: Manages novel metadata including characters, plots, settings, and continuity rules. Use when working with document_agent, knowledge_agent, character extraction, plot anchors, world settings, or continuity validation.
---

# Novel Metadata Skill

## Purpose
Provides structured metadata for immersive novel interaction: characters, plots, scene settings, and continuity constraints.

## Sub-skills
- **character-metadata**: Character traits, relationships, development arcs
- **plot-metadata**: Plot anchors, timeline, key events
- **scene-metadata**: World settings, locations, key items
- **continuity-rules**: Validation rules for consistency

## Key Interfaces
- `get_context_for_scene(document_id, character_name, chapter)` → context dict
- `validate_scene(scene, character_name, chapter)` → validation result

## Data Locations
- Characters: `data/characters/{document_id}/characters.json`
- Plots: `data/plots/{document_id}/`
- Settings: `data/settings/{document_id}/settings.json`

## When Other Skills Need This
- StorylineControl requires: plot anchors, character constraints
- ImageGen requires: character appearance, scene descriptions
- Voice requires: character voice mapping
```

---

### 3.2 StorylineControl Skill（故事线控制 Skill）

#### 3.2.1 定位
- **开发时**：指导 Agent 如何实现偏离度评估、软/硬约束、引导逻辑
- **运行时**：评估用户输入对故事线的影响，在保持主线的同时最大化自由度

#### 3.2.2 依赖关系
- **requires**: NovelMetadata（情节锚点、角色约束、世界观）
- **provides**: 偏离度评估结果、引导建议、是否允许继续

#### 3.2.3 目录结构

```
.cursor/skills/storyline-control/
├── SKILL.md
├── reference.md          # 分层约束、引导策略
└── examples.md           # 评估示例

agent/skills/storyline_control/   # 运行时实现
├── __init__.py
├── divergence_manager.py
└── constraint_layers.py
```

#### 3.2.4 Cursor Agent Skill 示例

**`.cursor/skills/storyline-control/SKILL.md`**

```markdown
---
name: storyline-control
description: Evaluates user choices against story plot, manages divergence levels, and balances storyline adherence with character freedom. Use when implementing InputEvaluator, divergence logic, plot anchors, or user choice validation.
---

# Storyline Control Skill

## Purpose
Balance story coherence with player freedom through layered constraints.

## Constraint Layers
1. **Hard**: Timeline, irreversible events, core world rules
2. **Medium**: Plot anchors, key relationships, important settings
3. **Soft**: Character personality, emotional logic, exploration

## Key Logic
- `evaluate_divergence(user_input, context)` → {level, message, guidance, allow_continue}
- Hard violation → suggest alternatives, do not allow
- Medium → allow with guidance
- Soft → allow, record for consistency

## Requires
- NovelMetadata: plot_anchors, character_constraints, world_rules

## Provides To
- InputEvaluator: divergence assessment
- SceneGenerator: guidance hints for next scene
```

---

### 3.3 ImageGeneration Skill（图像生成 Skill）

#### 3.3.1 定位
- **开发时**：指导 Agent 如何从场景提取视觉元素、构建分层提示词
- **运行时**：将 narrative、key_elements、emotion_state 转为高质量图像提示

#### 3.3.2 依赖关系
- **requires**: NovelMetadata（角色外观、场景设定）
- **consumes**: SceneGenerator 输出的 narrative、key_elements、emotion_state

#### 3.3.3 目录结构

```
.cursor/skills/image-generation/
├── SKILL.md
├── prompt-templates.md    # 提示词模板
└── reference.md

agent/skills/image_generation/
├── __init__.py
├── visual_extractor.py   # LLM 提取视觉元素
├── prompt_builder.py      # 分层提示词构建
└── style_selector.py     # 风格选择逻辑
```

#### 3.3.4 Cursor Agent Skill 示例

**`.cursor/skills/image-generation/SKILL.md`**

```markdown
---
name: image-generation
description: Converts scene narratives into optimized image generation prompts. Use when working with ImageGenerator, visual description extraction, prompt building, or image style selection.
---

# Image Generation Skill

## Purpose
Transform scene text into structured, layered prompts for image APIs.

## Prompt Structure
[Style] + [Subjects] + [Environment] + [Composition] + [Lighting] + [Atmosphere]

## Key Steps
1. Extract visual elements via LLM (main_subjects, environment, actions, details, lighting)
2. Analyze composition needs (dialogue→medium shot, action→dynamic angle)
3. Build layered prompt per template
4. Auto-select style from scene mood

## Requires
- NovelMetadata: character appearance, scene settings
- Scene: narrative, key_elements, emotion_state

## Output
- Enhanced prompt string for image API
- Recommended style (realistic, anime, painting, sketch, 3d)
```

---

### 3.4 MemoryArchitecture Skill（记忆架构 Skill）

#### 3.4.1 定位
- **开发时**：指导 Agent 理解分层记忆、向量检索、记忆整合
- **运行时**：管理情景/语义/工作/长期记忆，提供相关记忆检索

#### 3.4.2 依赖关系
- **consumes**: SceneGenerator 的 memory_update、progress_info
- **provides**: 相关记忆给 SceneGenerator、InputEvaluator、StorylineControl

#### 3.4.3 目录结构

```
.cursor/skills/memory-architecture/
├── SKILL.md
├── reference.md          # 分层记忆、检索策略
└── schemas/
    └── memory_schema.json

agent/skills/memory/
├── __init__.py
├── enhanced_memory_manager.py
├── episodic_memory.py
├── semantic_memory.py
└── vector_store.py
```

#### 3.4.4 Cursor Agent Skill 示例

**`.cursor/skills/memory-architecture/SKILL.md`**

```markdown
---
name: memory-architecture
description: Manages episodic, semantic, working, and long-term memory with vector retrieval. Use when implementing MemoryManager, cross-chapter recall, memory consolidation, or semantic search.
---

# Memory Architecture Skill

## Memory Layers
- **Episodic**: Specific events, timestamps, emotional tags
- **Semantic**: Relationships, world knowledge, concepts
- **Working**: Current scene context, recent choices
- **Long-term**: Important summaries, character arcs

## Key Operations
- `store_memory(type, content, importance)` 
- `retrieve_relevant_memories(query, max_results)` → scored list
- `consolidate_memories(chapter)` at chapter end

## Scoring Formula
relevance = importance×0.4 + similarity×0.3 + access_freq×0.2 + time_decay×0.1

## Provides To
- SceneGenerator: cross_chapter_memory
- InputEvaluator: related_memories
- StorylineControl: plot-relevant memories
```

---

### 3.5 VoiceGeneration Skill（语音生成 Skill）

#### 3.5.1 定位
- **开发时**：指导 Agent 排查 Token、音色、对话提取、异步调用等问题
- **运行时**：从场景中提取对话，选择音色，调用 TTS API 生成语音

#### 3.5.2 依赖关系
- **requires**: NovelMetadata（角色音色映射）
- **consumes**: SceneGenerator 的 narrative（提取对话）

#### 3.5.3 目录结构

```
.cursor/skills/voice-generation/
├── SKILL.md
├── troubleshooting.md    # Token、音色、API 错误排查
└── reference.md

agent/skills/voice/
├── __init__.py
├── voice_service.py      # 现有实现，按 Skill 规范重构
├── dialogue_extractor.py
└── voice_selector.py
```

#### 3.5.4 Cursor Agent Skill 示例

**`.cursor/skills/voice-generation/SKILL.md`**

```markdown
---
name: voice-generation
description: Converts scene dialogues to speech via TTS API. Use when debugging VoiceService, token authentication, voice selection, dialogue extraction, or TTS integration.
---

# Voice Generation Skill

## Purpose
Extract dialogues from narrative, select voice per character, generate audio.

## Key Flow
1. Extract dialogues: LLM-first, fallback to rule-based (speaker: content)
2. Select voice: character_info.voice_type → LLM selection → rule fallback
3. Generate: HTTP/WebSocket API with Bearer; {token} auth

## Troubleshooting
- **403/401**: Check token format "Bearer; {token}", not "Bearer {token}"
- **Resource not granted**: Try free voices (BV001_streaming, BV002_streaming)
- **No dialogues**: Improve extract_dialogues, check narrative format

## Requires
- NovelMetadata: character voice mapping in characters.json
- Scene: narrative for dialogue extraction

## Auth Format
Headers: Authorization: "Bearer; {access_token}"
Token from VolcEngine console, NOT API Key
```

---

## 四、Skill 编排与运行时架构

### 4.1 Skill 注册表

**`agent/skills/registry.py`**

```python
from typing import Dict, List, Type, Any
from dataclasses import dataclass

@dataclass
class SkillDefinition:
    name: str
    description: str
    requires: List[str]      # 依赖的 Skill 名称
    provides: List[str]      # 提供给其他组件的输出
    module_path: str        # 运行时模块路径

SKILL_REGISTRY = {
    "novel-metadata": SkillDefinition(
        name="novel-metadata",
        description="Novel metadata management",
        requires=[],
        provides=["character_context", "plot_anchors", "world_settings"],
        module_path="agent.skills.novel_metadata"
    ),
    "storyline-control": SkillDefinition(
        name="storyline-control",
        description="Storyline divergence control",
        requires=["novel-metadata"],
        provides=["divergence_evaluation", "guidance"],
        module_path="agent.skills.storyline_control"
    ),
    "image-generation": SkillDefinition(
        name="image-generation",
        description="Scene-to-image prompt optimization",
        requires=["novel-metadata"],
        provides=["image_prompt", "style_recommendation"],
        module_path="agent.skills.image_generation"
    ),
    "memory-architecture": SkillDefinition(
        name="memory-architecture",
        description="Layered memory management",
        requires=[],
        provides=["relevant_memories", "memory_update"],
        module_path="agent.skills.memory"
    ),
    "voice-generation": SkillDefinition(
        name="voice-generation",
        description="Dialogue to speech conversion",
        requires=["novel-metadata"],
        provides=["audio_paths", "dialogue_audio"],
        module_path="agent.skills.voice"
    ),
}
```

### 4.2 Skill 编排器

**`agent/skills/orchestrator.py`**

```python
class SkillOrchestrator:
    """协调各 Skill 的加载、依赖解析与调用"""
    
    def __init__(self, document_id: str):
        self.document_id = document_id
        self.skills: Dict[str, Any] = {}
        self._load_skills()
    
    def _load_skills(self):
        """按依赖顺序加载 Skill"""
        loaded = set()
        
        def load_skill(name: str):
            if name in loaded:
                return
            definition = SKILL_REGISTRY[name]
            for req in definition.requires:
                load_skill(req)
            self.skills[name] = self._instantiate_skill(definition)
            loaded.add(name)
        
        for skill_name in SKILL_REGISTRY:
            load_skill(skill_name)
    
    def get_context_for_scene(self, character_name: str, chapter: int) -> Dict:
        """聚合各 Skill 输出，生成场景上下文"""
        metadata = self.skills["novel-metadata"].get_context(character_name, chapter)
        memories = self.skills["memory-architecture"].retrieve(metadata.get("summary", ""))
        
        return {
            **metadata,
            "cross_chapter_memory": memories
        }
    
    def evaluate_input(self, user_input: str, context: Dict) -> Dict:
        """调用 StorylineControl 评估输入"""
        return self.skills["storyline-control"].evaluate(user_input, context)
    
    def generate_image_prompt(self, scene: Dict) -> str:
        """调用 ImageGeneration 生成提示词"""
        return self.skills["image-generation"].build_prompt(scene)
    
    def generate_voice_for_scene(self, scene: Dict) -> Dict:
        """调用 VoiceGeneration 生成语音"""
        return self.skills["voice-generation"].generate(scene)
```

### 4.3 与 InteractionAgent 的集成

```python
# interaction_agent.py 中的改动
class InteractionAgent:
    def __init__(self, config):
        # 使用 SkillOrchestrator 替代直接依赖各模块
        self.orchestrator = SkillOrchestrator(config.get('document_id'))
        
        # 保留原有接口，内部委托给 orchestrator
        self.scene_generator = SceneGenerator(...)  # 接收 orchestrator 提供的 context
        self.input_evaluator = InputEvaluator(...)  # 使用 orchestrator.evaluate_input
        self.memory_manager = self.orchestrator.skills["memory-architecture"]
        self.image_generator = self.orchestrator.skills["image-generation"]
        self.voice_service = self.orchestrator.skills["voice-generation"]
```

---

## 五、目录结构总览

```
AIFoundationAgent/
├── .cursor/
│   └── skills/
│       ├── novel-metadata/           # 开发时 Skill
│       │   ├── SKILL.md
│       │   ├── sub-skills/
│       │   │   ├── character-metadata/
│       │   │   ├── plot-metadata/
│       │   │   ├── scene-metadata/
│       │   │   └── continuity-rules/
│       │   └── reference.md
│       ├── storyline-control/
│       │   ├── SKILL.md
│       │   └── reference.md
│       ├── image-generation/
│       │   ├── SKILL.md
│       │   └── prompt-templates.md
│       ├── memory-architecture/
│       │   ├── SKILL.md
│       │   └── reference.md
│       └── voice-generation/
│           ├── SKILL.md
│           └── troubleshooting.md
│
├── agent/
│   ├── core/                        # 保留现有核心逻辑
│   │   ├── document_agent.py
│   │   ├── knowledge_agent.py
│   │   └── interaction/
│   │       ├── interaction_agent.py
│   │       ├── scene_generator.py
│   │       └── ...
│   │
│   └── skills/                      # 运行时 Skill 实现
│       ├── __init__.py
│       ├── registry.py              # Skill 注册表
│       ├── orchestrator.py           # Skill 编排器
│       ├── novel_metadata/
│       │   ├── __init__.py
│       │   └── metadata_manager.py
│       ├── storyline_control/
│       │   ├── __init__.py
│       │   └── divergence_manager.py
│       ├── image_generation/
│       │   ├── __init__.py
│       │   ├── visual_extractor.py
│       │   └── prompt_builder.py
│       ├── memory/
│       │   ├── __init__.py
│       │   └── enhanced_memory_manager.py
│       └── voice/
│           ├── __init__.py
│           └── voice_service.py
│
├── data/
│   └── books/                       # 每本书作为 Book Skill 包
│       └── {document_id}/
│           ├── SKILL.md             # 本书元数据入口
│           ├── characters.json
│           ├── plots.json
│           ├── settings.json
│           └── ...
│
└── DESIGN_SKILL_BASED_ARCHITECTURE.md  # 本文档
```

---

## 六、实施路线图

### Phase 1：Skill 骨架（1–2 周）
1. 创建 `.cursor/skills/` 下 5 个主 Skill 的 SKILL.md
2. 创建 `agent/skills/` 目录与 `registry.py`、`orchestrator.py`
3. 定义各 Skill 的接口（方法签名、输入输出结构）

### Phase 2：运行时 Skill 实现（2–3 周）
1. 将现有逻辑迁移到 `agent/skills/` 对应模块
2. 实现 NovelMetadata Skill（含 Book Skill 加载）
3. 实现 StorylineControl Skill
4. 实现 MemoryArchitecture Skill
5. 实现 ImageGeneration Skill
6. 实现 VoiceGeneration Skill

### Phase 3：编排与集成（1 周）
1. 完善 SkillOrchestrator 的依赖解析与调用链
2. 将 InteractionAgent 切换为使用 Orchestrator
3. 端到端测试各 Skill 协作

### Phase 4：子 Skill 与 Book Skill（1–2 周）
1. 为 NovelMetadata 添加 4 个子 Skill
2. 实现 Book Skill 的加载与校验
3. 补充各 Skill 的 reference.md、troubleshooting.md

---

## 七、方案优势总结

| 优势 | 说明 |
|------|------|
| **可发现性** | Agent 通过 description 自动识别何时加载哪个 Skill |
| **可维护性** | 每个 Skill 职责清晰，修改影响范围可控 |
| **可扩展性** | 新书、新能力以新 Skill 形式加入，无需改动核心 |
| **可测试性** | 各 Skill 可独立单元测试 |
| **知识传承** | SKILL.md 与 reference 形成项目知识库 |
| **关系显式化** | requires/provides 明确依赖，便于理解和重构 |

---

## 八、与方案 1 的对比

| 维度 | 方案 1（DESIGN_OPTIMIZATION.md） | 方案 2（本方案） |
|------|----------------------------------|------------------|
| 组织方式 | 按功能模块（MetadataManager、DivergenceManager 等） | 按 Skill 划分，开发时 + 运行时双层 |
| 元数据 | 集中在 MetadataManager | 每本书为 Book Skill，可独立加载 |
| 依赖关系 | 隐式，通过代码调用体现 | 显式，通过 registry 的 requires/provides |
| Agent 支持 | 无专门指导 | 每个能力对应 Cursor Skill，开发时自动加载 |
| 扩展方式 | 新增类/模块 | 新增 Skill 包 |
| 知识沉淀 | 依赖代码注释与文档 | Skill 的 SKILL.md、reference 即文档 |
