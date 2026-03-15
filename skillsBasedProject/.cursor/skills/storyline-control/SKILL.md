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
- `evaluate(user_input, context)` → {level, message, guidance, allow_continue}
- Hard violation → suggest alternatives, do not allow
- Medium → allow with guidance
- Soft → allow, record for consistency

## Requires
- NovelMetadata: plot_anchors, character_constraints, world_rules

## Provides To
- InputEvaluator: divergence assessment
- SceneGenerator: guidance hints for next scene
