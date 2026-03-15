# 优化方案实施指南

## 快速开始

本指南将帮助你逐步实施优化方案，建议按照优先级顺序进行。

---

## Phase 1: 核心功能优化

### 1.1 记忆管理系统重构

#### 步骤 1: 创建新的记忆管理器

**文件：`agent/core/interaction/enhanced_memory_manager.py`**

```python
from typing import Dict, Any, List, Optional
import logging
import time
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

logger = logging.getLogger(__name__)

class EnhancedMemoryManager:
    """增强的记忆管理器"""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("./data/memories")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化向量模型
        self.encoder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # 初始化向量存储
        self.dimension = 384  # 模型维度
        self.index = faiss.IndexFlatL2(self.dimension)
        self.memory_store = []
        
        # 记忆类型
        self.episodic_memory = []
        self.semantic_memory = {}
        self.working_memory = {}
        self.long_term_memory = []
    
    def store_memory(self, memory_type: str, content: Dict, 
                    importance: float = 0.5,
                    related_memories: List[str] = None):
        """存储记忆"""
        memory_id = f"mem_{int(time.time() * 1000)}"
        
        memory_item = {
            'id': memory_id,
            'type': memory_type,
            'content': content,
            'importance': importance,
            'timestamp': time.time(),
            'related_memories': related_memories or [],
            'access_count': 0,
            'last_accessed': time.time()
        }
        
        # 存储到对应类型
        if memory_type == 'episodic':
            self.episodic_memory.append(memory_item)
        elif memory_type == 'semantic':
            key = content.get('key', 'general')
            if key not in self.semantic_memory:
                self.semantic_memory[key] = []
            self.semantic_memory[key].append(memory_item)
        elif memory_type == 'long_term':
            self.long_term_memory.append(memory_item)
        
        # 添加到向量索引
        text = self._extract_text_from_content(content)
        vector = self.encoder.encode([text])[0]
        self.index.add(np.array([vector]).astype('float32'))
        self.memory_store.append(memory_item)
        
        logger.info(f"存储记忆: {memory_id}, 类型: {memory_type}, 重要性: {importance}")
    
    def retrieve_relevant_memories(self, query: str, max_results: int = 10) -> List[Dict]:
        """检索相关记忆"""
        if not self.memory_store:
            return []
        
        # 向量化查询
        query_vector = self.encoder.encode([query])[0]
        
        # 搜索相似记忆
        k = min(max_results, len(self.memory_store))
        distances, indices = self.index.search(
            np.array([query_vector]).astype('float32'), 
            k
        )
        
        # 获取记忆并评分
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < len(self.memory_store):
                memory = self.memory_store[idx].copy()
                memory['similarity_score'] = 1 / (1 + distance)  # 转换为相似度分数
                memory['access_count'] += 1
                memory['last_accessed'] = time.time()
                results.append(memory)
        
        # 综合评分排序
        scored_results = self._score_memories(results, query)
        return scored_results[:max_results]
    
    def _score_memories(self, memories: List[Dict], query: str) -> List[Dict]:
        """综合评分记忆"""
        scored = []
        current_time = time.time()
        
        for memory in memories:
            # 时间衰减因子（越新越重要）
            time_decay = np.exp(-(current_time - memory['timestamp']) / (30 * 24 * 3600))  # 30天衰减
            
            # 综合评分
            score = (
                memory['importance'] * 0.4 +
                memory.get('similarity_score', 0) * 0.3 +
                min(memory['access_count'] / 10, 1.0) * 0.2 +
                time_decay * 0.1
            )
            
            memory['relevance_score'] = score
            scored.append(memory)
        
        return sorted(scored, key=lambda x: x['relevance_score'], reverse=True)
    
    def _extract_text_from_content(self, content: Dict) -> str:
        """从内容中提取文本"""
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            # 提取所有文本字段
            texts = []
            for key, value in content.items():
                if isinstance(value, str):
                    texts.append(value)
                elif isinstance(value, list):
                    texts.extend([str(v) for v in value if isinstance(v, str)])
            return ' '.join(texts)
        return str(content)
    
    def save_memories(self, file_path: Path = None):
        """保存记忆到文件"""
        file_path = file_path or self.data_dir / "memories.json"
        
        data = {
            'episodic_memory': self.episodic_memory,
            'semantic_memory': self.semantic_memory,
            'long_term_memory': self.long_term_memory,
            'memory_store': self.memory_store
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"记忆已保存到: {file_path}")
    
    def load_memories(self, file_path: Path = None):
        """从文件加载记忆"""
        file_path = file_path or self.data_dir / "memories.json"
        
        if not file_path.exists():
            logger.warning(f"记忆文件不存在: {file_path}")
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.episodic_memory = data.get('episodic_memory', [])
        self.semantic_memory = data.get('semantic_memory', {})
        self.long_term_memory = data.get('long_term_memory', [])
        self.memory_store = data.get('memory_store', [])
        
        # 重建向量索引
        if self.memory_store:
            vectors = []
            for memory in self.memory_store:
                text = self._extract_text_from_content(memory['content'])
                vector = self.encoder.encode([text])[0]
                vectors.append(vector)
            
            if vectors:
                self.index = faiss.IndexFlatL2(self.dimension)
                self.index.add(np.array(vectors).astype('float32'))
        
        logger.info(f"记忆已从文件加载: {file_path}")
```

#### 步骤 2: 更新 InteractionAgent 使用新的记忆管理器

在 `interaction_agent.py` 中：

```python
# 替换旧的 MemoryManager
from agent.core.interaction.enhanced_memory_manager import EnhancedMemoryManager

class InteractionAgent:
    def __init__(self, ...):
        # ...
        self.memory_manager = EnhancedMemoryManager(data_dir=Path(config.get('data_dir', './data')))
```

### 1.2 元数据管理器实现

#### 步骤 1: 创建元数据管理器

**文件：`agent/core/metadata_manager.py`**

```python
from typing import Dict, Any, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MetadataManager:
    """元数据管理器"""
    
    def __init__(self, document_id: str, data_dir: Path):
        self.document_id = document_id
        self.data_dir = data_dir
        
        # 加载元数据
        self.characters = self._load_characters()
        self.settings = self._load_settings()
        self.plots = self._load_plots()
    
    def _load_characters(self) -> Dict:
        """加载角色信息"""
        file_path = self.data_dir / 'characters' / self.document_id / 'characters.json'
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _load_settings(self) -> Dict:
        """加载世界观设定"""
        file_path = self.data_dir / 'settings' / self.document_id / 'settings.json'
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _load_plots(self) -> Dict:
        """加载情节信息"""
        file_path = self.data_dir / 'plots' / self.document_id / 'plots.json'
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def get_context_for_scene(self, character_name: str, chapter: int) -> Dict:
        """获取场景生成的上下文"""
        character_info = self.characters.get(character_name, {})
        
        # 获取相关设定
        relevant_settings = self._get_relevant_settings(chapter)
        
        # 获取情节锚点
        plot_anchors = self._get_plot_anchors(chapter)
        
        return {
            'character_context': {
                'name': character_name,
                'info': character_info,
                'relationships': self._get_character_relationships(character_name)
            },
            'world_context': relevant_settings,
            'plot_anchors': plot_anchors,
            'continuity_constraints': self._get_continuity_constraints(character_name, chapter)
        }
    
    def _get_relevant_settings(self, chapter: int) -> List[Dict]:
        """获取相关设定"""
        # 根据章节返回相关设定
        return self.settings.get('settings', [])
    
    def _get_plot_anchors(self, chapter: int) -> List[Dict]:
        """获取情节锚点"""
        # 返回当前章节及后续章节的关键情节节点
        anchors = []
        for plot in self.plots.get('plots', []):
            if plot.get('chapter', 0) >= chapter:
                anchors.append(plot)
        return anchors[:5]  # 返回最近5个锚点
    
    def _get_character_relationships(self, character_name: str) -> Dict:
        """获取角色关系"""
        character_info = self.characters.get(character_name, {})
        return character_info.get('relationships', {})
    
    def _get_continuity_constraints(self, character_name: str, chapter: int) -> Dict:
        """获取连续性约束"""
        return {
            'character_traits': self.characters.get(character_name, {}).get('traits', []),
            'world_rules': self.settings.get('rules', []),
            'timeline': self._get_timeline(chapter)
        }
    
    def _get_timeline(self, chapter: int) -> List[Dict]:
        """获取时间线"""
        # 返回已发生的事件时间线
        timeline = []
        for plot in self.plots.get('plots', []):
            if plot.get('chapter', 0) < chapter:
                timeline.append(plot)
        return timeline
```

### 1.3 语音生成修复

#### 步骤 1: 添加Token验证和修复

在 `voice_service.py` 的 `set_token` 方法中添加：

```python
def set_token(self, token: str) -> None:
    """设置Token，带验证和修复"""
    if not token:
        logger.warning("Token为空")
        self.token = None
        return
    
    # 清理和修复Token
    fixed_token = token.strip()
    
    # 移除Bearer前缀
    if fixed_token.startswith('Bearer'):
        fixed_token = fixed_token.replace('Bearer', '').strip()
        if fixed_token.startswith(';'):
            fixed_token = fixed_token[1:].strip()
    
    # 验证Token
    if len(fixed_token) < 50:
        logger.warning(f"Token长度异常短 ({len(fixed_token)}字符)")
    
    self.token = fixed_token
    logger.info(f"Token已设置，长度: {len(self.token)}")
```

---

## Phase 2: 体验优化

### 2.1 偏离度管理器

**文件：`agent/core/interaction/divergence_manager.py`**

```python
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class DivergenceManager:
    """偏离度管理器"""
    
    def __init__(self, client, llm_model):
        self.client = client
        self.llm_model = llm_model
    
    def evaluate_divergence(self, user_input: str, context: Dict) -> Dict:
        """评估偏离度"""
        # 检查硬约束
        hard_violations = self._check_hard_constraints(user_input, context)
        if hard_violations:
            return {
                'level': 'hard_violation',
                'message': '该选择违背了故事的核心设定',
                'suggestions': self._generate_alternatives(user_input, context)
            }
        
        # 检查中等约束
        medium_violations = self._check_medium_constraints(user_input, context)
        if medium_violations:
            return {
                'level': 'medium_divergence',
                'message': '该选择可能偏离主线，但可以接受',
                'guidance': self._generate_guidance(user_input, context),
                'allow_continue': True
            }
        
        return {
            'level': 'on_track',
            'message': '选择合理，继续故事'
        }
    
    def _check_hard_constraints(self, user_input: str, context: Dict) -> List[str]:
        """检查硬约束"""
        violations = []
        
        # 检查时间线
        timeline = context.get('timeline', [])
        # 实现时间线检查逻辑
        
        # 检查核心设定
        world_rules = context.get('world_rules', [])
        # 实现设定检查逻辑
        
        return violations
    
    def _generate_guidance(self, user_input: str, context: Dict) -> str:
        """生成引导性提示"""
        prompt = f"""用户的选择是：{user_input}
        
请生成一个引导性提示，帮助用户理解这个选择的影响，但不要强制改变用户的选择。
提示应该：
1. 说明选择可能带来的影响
2. 提供替代建议（可选）
3. 保持友好和鼓励的语气

只返回提示文本，不要其他内容。"""
        
        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )
        
        return response.choices[0].message.content
```

---

## Phase 3: UI优化

### 3.1 添加自定义CSS

在 `app.py` 开头添加：

```python
def load_custom_css():
    """加载自定义CSS"""
    st.markdown("""
    <style>
        /* 主色调 */
        .main {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        /* 场景卡片 */
        .scene-card {
            background: rgba(30, 41, 59, 0.9);
            border-radius: 16px;
            padding: 2rem;
            margin: 1rem 0;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
        }
        
        /* 按钮样式 */
        .stButton > button {
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            color: white;
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1.5rem;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }
    </style>
    """, unsafe_allow_html=True)
```

---

## 测试建议

### 单元测试示例

**文件：`tests/test_enhanced_memory.py`**

```python
import pytest
from agent.core.interaction.enhanced_memory_manager import EnhancedMemoryManager
from pathlib import Path

def test_memory_storage():
    """测试记忆存储"""
    manager = EnhancedMemoryManager()
    
    manager.store_memory(
        memory_type='episodic',
        content={'event': '角色遇到了重要人物'},
        importance=0.8
    )
    
    assert len(manager.episodic_memory) == 1

def test_memory_retrieval():
    """测试记忆检索"""
    manager = EnhancedMemoryManager()
    
    manager.store_memory(
        memory_type='episodic',
        content={'event': '角色遇到了重要人物'},
        importance=0.8
    )
    
    results = manager.retrieve_relevant_memories('重要人物', max_results=5)
    assert len(results) > 0
    assert results[0]['type'] == 'episodic'
```

---

## 部署检查清单

- [ ] 更新 requirements.txt，添加新依赖
- [ ] 运行单元测试
- [ ] 测试记忆管理功能
- [ ] 测试元数据管理器
- [ ] 测试语音生成修复
- [ ] 测试UI优化效果
- [ ] 更新文档

---

## 常见问题

### Q: 向量模型太大，加载慢怎么办？
A: 可以使用更小的模型，如 `paraphrase-multilingual-MiniLM-L12-v2`，或者延迟加载。

### Q: FAISS索引占用内存太大？
A: 可以定期保存索引到磁盘，或者使用更高效的索引类型（如IVF）。

### Q: 语音生成仍然失败？
A: 检查Token格式，确保使用正确的access_token而非API Key。

---

## 下一步

1. 按照Phase顺序逐步实施
2. 每个Phase完成后进行测试
3. 收集用户反馈，迭代优化
4. 参考 DESIGN_OPTIMIZATION.md 了解详细设计
