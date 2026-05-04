---
name: rmbg
description: 使用本地 BiRefNet (RMBG-2.0) 模型去除图像背景，输出带透明通道的 PNG。用户说"去背景"、"抠图"、"移除背景"、"去除背景"、"remove background"时触发。提供图片路径且上下文与背景移除相关也触发。
---

# 去背景（rmbg）

使用本机 BiRefNet 模型对图像进行背景移除，输出 RGBA 透明 PNG。

## 输入解析

从用户消息中提取以下参数：

| 参数 | 标志 | 必填 | 说明 |
|------|------|------|------|
| 输入图像 | `-i` | ✓ | 支持绝对或相对路径 |
| 模型目录 | `-m` | ✓ | 模型目录，需包含 BiRefNet_config.py、birefnet.py 和 model.safetensors |
| 输出路径 | `-o` | 否 | 默认：`输入文件名_rmbg.png`；`--white-bg` 模式则为 `_whitebg.jpg` |
| 阈值 | `-t` | 否 | 默认 0.5，范围 0.3-0.7 |
| 白底模式 | `--white-bg` | 否 | 输出白底 RGB 图片（JPEG），而非透明 PNG |
| 跳过边缘优化 | `--no-edge-refine` | 否 | 关闭膨胀+高斯模糊，速度更快但边缘可能较粗糙 |

**阈值场景建议：**

| 场景 | 建议阈值 | 说明 |
|------|---------|------|
| 发丝/半透明材质 | 0.3-0.4 | 保留半透明细节 |
| 通用场景（默认） | 0.5 | 平衡细节保留与背景清除 |
| 电商白底图 | 0.6 | 确保边缘干净 |

若用户未提供输入路径或模型目录，用 **AskUserQuestion** 工具询问。

## 执行步骤

### 1. 告知用户

说明正在加载模型（首次约需数秒），让用户稍等。

### 2. 运行脚本

从项目根目录执行：

```bash
python .claude/skills/rmbg/scripts/rmbg_process.py -i "<输入图像路径>" -m "<模型目录路径>" [-o "<输出路径>"] [-t 0.5] [--white-bg] [--no-edge-refine]
```

- CUDA 可用时自动使用 GPU，否则回退 CPU。GPU 上约 50-80ms（RTX 3060），CPU 约 2-5 秒（8 核以上）。
- 脚本输出 `Saved: <路径>` 表示成功。

### 3. 报告结果

**成功**：告知输出文件路径，可附上简要说明（如文件大小、原始分辨率）。

**失败**：展示错误信息，并按以下思路排查：

| 错误特征 | 可能原因 | 建议 |
|----------|----------|------|
| 找不到模型文件 | 模型路径不对 | 查看 `references/setup.md` |
| `ModuleNotFoundError` | 依赖未安装 | 运行安装命令（见下方） |
| 输入文件不存在 | 路径错误 | 请用户确认路径 |
| CUDA out of memory | 显存不足 | 脚本自动回退 CPU，耐心等待即可 |
| 模型文件加载失败 | 网络问题或文件不完整 | 检查网络，确保能访问 Hugging Face Hub |

依赖安装命令：
```bash
pip install torch torchvision transformers safetensors pillow numpy timm kornia
```

其中 `timm` 需固定版本 `==0.9.16`。如需边缘优化（`--no-edge-refine` 关闭），还需 `scipy`：
```bash
pip install scipy
```

---

**注意**：默认输出 RGBA 透明 PNG；`--white-bg` 模式输出白底 RGB JPEG。模型内部以 1024×1024 推理，mask 自动缩放回原图尺寸。遇到模型安装问题，参考 `references/setup.md`。
