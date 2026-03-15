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
