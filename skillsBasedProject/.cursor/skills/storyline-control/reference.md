# Storyline Control Reference

## Divergence Levels
- 0: on_track
- 1-2: soft_divergence
- 3-4: medium_divergence
- 5: hard_violation

## Evaluation Output
```json
{
  "level": "on_track|soft_divergence|medium_divergence|hard_violation",
  "message": "...",
  "guidance": "...",
  "allow_continue": true|false,
  "divergence": {"level": 0-5, "description": "...", "key_changes": []}
}
```
