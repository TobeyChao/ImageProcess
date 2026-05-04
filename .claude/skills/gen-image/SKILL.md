---
name: gen-image
description: 使用 Gemini API 生成图片。当用户想生成图片、画图、创建图像、制作图、出图时必须触发此 skill。触发词包括：生成图片、画一张、帮我画、生图、generate image、create image、make an image、draw a picture 等。即使用户描述很简短（如"画只猫"、"来张风景图"），也应触发此 skill。
---

## 目的

调用 Gemini 图像生成脚本，将用户的描述转化为实际图片并保存到项目输出目录。

## 脚本与输出

从**项目根目录**运行：
- 脚本：`.claude/skills/gen-image/scripts/gen_image.py`
- 默认输出：`local/output/`

## 步骤

### 第一步：解析参数

从用户的自然语言中提取：

**1. 图片描述**（必须）

**2. 宽高比**（可选，默认 `1:1`）

| 用户表达 | 参数值 |
|---------|-------|
| 横版、宽屏、电脑壁纸 | `16:9` |
| 竖版、手机壁纸、竖屏 | `9:16` |
| 方图、正方形 | `1:1` |
| 直接写出，如 "4:3" | 直接使用 |

支持的值：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`3:2`、`2:3`、`4:5`、`5:4`、`21:9`

**3. 分辨率**（可选，默认 `1K`）

| 用户表达 | 参数值 |
|---------|-------|
| 高清、HD | `2K` |
| 超高清、4K | `4K` |
| 小图、缩略图 | `512` |
| 未提及 | `1K` |

### 第二步：优化 prompt 为英文

将用户的描述（无论中英文）转化为高质量英文 prompt：
- 补充画风、光线、构图等细节，让图片更精美
- 忠实用户核心意图，不过度发挥
- 长度控制在 1-3 句话

**示例：**

| 用户输入 | 优化后的英文 prompt |
|---------|-------------------|
| 一只橘猫 | A fluffy orange tabby cat sitting gracefully, soft natural lighting, photorealistic |
| 日落海边风景 | Golden sunset over a calm ocean beach, warm orange and pink sky reflected on the water, cinematic landscape photography |
| 科技感的城市夜景 | Futuristic city skyline at night, glowing neon lights, cyberpunk aesthetic, long exposure photography |

### 第三步：运行脚本

从项目根目录执行：

```bash
python .claude/skills/gen-image/scripts/gen_image.py -p "<优化后的英文prompt>" [-r <宽高比>] [-s <分辨率>]
```

只有非默认值才需要传 `-r` 和 `-s`，输出目录默认为 `local/output`，无需额外指定。

### 第四步：告知结果

成功后告诉用户：
- 图片文件名和路径（`local/output/<filename>`）
- 实际使用的 prompt（供参考）

脚本报错时，说明错误原因并给出建议。

| 错误特征 | 可能原因 | 建议 |
|---------|---------|------|
| `User location is not supported` | 当前地区不支持 Gemini 图片生成 API | 需使用代理或等待 Google 开放该地区 |
| `API key not valid` | 密钥过期或被吊销 | 更新 `.claude/settings.json` 中的 `GEMINI_API_KEY` |
| `Resource exhausted` | API 配额用尽 | 稍后重试或切换密钥 |
| `ModuleNotFoundError` | 依赖未安装 | `pip install google-genai pillow` |

## 注意

- API 密钥已通过项目 `.claude/settings.json` 的 `env.GEMINI_API_KEY` 配置，无需手动传入
- 需要联网，Gemini API 有频率限制
- 同时要多张图时，依次多次运行脚本



