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
- `retrieve(query, max_results)` → scored list
- `consolidate_memories(chapter)` at chapter end

## Scoring Formula
relevance = importance×0.4 + similarity×0.3 + access_freq×0.2 + time_decay×0.1

## Provides To
- SceneGenerator: cross_chapter_memory
- InputEvaluator: related_memories
- StorylineControl: plot-relevant memories
