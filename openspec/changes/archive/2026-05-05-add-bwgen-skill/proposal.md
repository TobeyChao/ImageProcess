## Why

bwdiff 黑白差分去背景需要用户提供同一主体在黑底和白底下的两张图，但用户很难直接拥有这种素材。bwgen 技能通过 Gemini API 从文字描述直接生成黑白双图，打通"文字→透明 PNG"的完整链路，且无需本地 GPU 或深度学习模型。

## What Changes

- 新增 `bwgen` 技能，接受文字描述作为输入
- 第一步调用 Gemini 文生图，生成纯黑底（#000000）的主体图
- 第二步调用 Gemini 图编辑，将黑底替换为纯白底（#FFFFFF），保持主体不变
- 输出黑白双图，可直接作为 bwdiff 的输入
- 复用现有 `GEMINI_API_KEY` 环境变量和 `google-genai` 依赖

## Capabilities

### New Capabilities

- `bwgen`: 通过 Gemini API 从文字描述生成黑白背景双图，作为 bwdiff 的前序输入

### Modified Capabilities

<!-- 无现有 capability 需要修改 -->

## Impact

- 新增文件：`.claude/skills/bwgen/SKILL.md`、`.claude/skills/bwgen/scripts/bw_gen.py`
- 依赖：`google-genai`（已有）、Gemini API 密钥（已配置）
- 与 `bwdiff` 技能串联，不修改现有技能
