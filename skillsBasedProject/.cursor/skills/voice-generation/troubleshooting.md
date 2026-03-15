# Voice Generation Troubleshooting

## 403 Errors
- Token format: "Bearer; {token}" (semicolon + space)
- Use access_token from VolcEngine console, not API Key

## No Dialogues Extracted
- Check narrative format: "角色名：对话内容"
- Fallback: rule-based extraction with "：" or ": "

## Resource Not Granted
- Try free voices: BV001_streaming, BV002_streaming
