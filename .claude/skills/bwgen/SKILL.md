---
name: bwgen
description: 使用 Gemini API 或阿里云百炼 Wan2.7 Pro 从文字描述生成黑白背景双图，作为 bwdiff 黑白差分去背景的前序步骤。用户说"生成黑白底图"、"bwgen"、或提到需要黑白背景素材时触发。
compatibility: 依赖 Gemini API 密钥（GEMINI_API_KEY）或阿里云百炼 API 密钥（DASHSCOPE_API_KEY），需联网，无需 GPU。
---

# 黑白背景图生成（bwgen）

通过 Gemini 或 Wan2.7 Pro 两步生成黑白背景双图：先从文字描述生成黑底图，再将黑底编辑为白底，输出可直接传入 bwdiff。

## 输入解析

从用户消息中提取以下参数：

| 参数 | 标志 | 必填 | 说明 |
|------|------|------|------|
| 图片描述 | `-p` | ✓ | 中英文均可，会自动追加"纯黑背景"要求 |
| 宽高比 | `-r` | 否 | 默认 `1:1`，支持 `1:1`、`16:9`、`9:16`、`4:3`、`3:4` 等 |
| 分辨率 | `-s` | 否 | 默认 `1K`，可选 `512`、`1K`、`2K`、`4K` |
| 输出目录 | `-o` | 否 | 默认 `local/output` |
| 模型 | `-m` | 否 | 默认 `gemini`，可选 `wan`（Wan2.7 Pro） |

若用户未提供描述文本，用 **AskUserQuestion** 工具询问。

## 执行步骤

### 1. 告知用户

说明将通过两步调用 Gemini API 生成黑白双图，需要两次 API 调用，请稍候。

### 2. 运行脚本

从项目根目录执行：

```bash
# 默认 Gemini
python .claude/skills/bwgen/scripts/bw_gen.py -p "<描述>" [-r <宽高比>] [-s <分辨率>] [-o <输出目录>]

# 使用 Wan2.7 Pro
python .claude/skills/bwgen/scripts/bw_gen.py -m wan -p "<描述>" [-r <宽高比>] [-s <分辨率>] [-o <输出目录>]
```

- Step 1：文生图，生成纯黑底（#000000）主体图
- Step 2：图编辑，将黑底替换为纯白底（#FFFFFF）
- 输出两个文件：`<slug>_black.png`、`<slug>_white.png`

**模型选择**：若用户未指定模型，默认用 Gemini。若用户提到"万象"、"wan"、"阿里"、"百炼"，则传 `-m wan`。

### 3. 报告结果

**成功**：告知两个输出文件路径，提示可继续使用 bwdiff 抠图：
```bash
python .claude/skills/bwdiff/scripts/bw_diff.py -b <xxx_black.png> -w <xxx_white.png>
```

**失败**：展示错误信息，并按以下思路排查：

| 错误特征 | 可能原因 | 建议 |
|----------|----------|------|
| `ModuleNotFoundError` | 依赖未安装 | `pip install google-genai pillow requests` |
| `API key not valid` | 密钥过期 | 更新 `.claude/settings.local.json` 中的 `GEMINI_API_KEY` |
| `Resource exhausted` | API 配额用尽 | 稍后重试或切换密钥/模型 |
| `User location is not supported` | 地区限制 | 尝试 `-m wan` 切换 Wan2.7，或使用代理 |
| `InvalidApiKey` | DashScope API 密钥无效 | 检查 `DASHSCOPE_API_KEY` 是否正确 |

依赖安装命令：
```bash
pip install google-genai pillow requests
```

---

**注意**：输出双图尺寸一致，可直接传入 bwdiff。两步生成约需 5-15 秒取决于模型和 API 响应速度。
