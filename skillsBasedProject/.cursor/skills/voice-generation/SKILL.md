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
