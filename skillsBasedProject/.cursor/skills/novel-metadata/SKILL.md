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
- `get_context(document_id, character_name, chapter)` → context dict
- `validate_scene(scene, character_name, chapter)` → validation result

## Data Locations
- Characters: `data/characters/{document_id}/characters.json` or `data/books/{document_id}/characters.json`
- Plots: `data/plots/{document_id}/plots.json`
- Settings: `data/settings/{document_id}/settings.json`

## When Other Skills Need This
- StorylineControl requires: plot anchors, character constraints
- ImageGen requires: character appearance, scene descriptions
- Voice requires: character voice mapping
