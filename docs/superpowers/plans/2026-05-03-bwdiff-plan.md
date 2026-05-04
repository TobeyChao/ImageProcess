# 黑白差分去背景 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **实际实现记录：** bwdiff 最终作为独立技能（`.claude/skills/bwdiff/`）而非 rmbg 子模块实现，拥有独立的 SKILL.md、脚本目录和触发规则。

**Goal:** 新增 bw_diff.py 脚本，通过黑底图/白底图像素差分计算 alpha 通道，替代深度学习实现轻量去背景。

**Architecture:** 独立技能（`.claude/skills/bwdiff/`），含 SKILL.md 和 scripts/bw_diff.py。脚本纯 numpy 向量化计算，无模型依赖，pillow 读写图像。

**Tech Stack:** Python 3, pillow, numpy

---

### Task 1: 创建 bw_diff.py 脚本

**Files:**
- Create: `.claude/skills/bwdiff/scripts/bw_diff.py`

- [ ] **Step 1: 创建脚本文件**

```python
import argparse
import numpy as np
from PIL import Image


def compute_alpha(black_img, white_img):
    """逐像素计算 alpha 通道和前景色。

    Args:
        black_img: (H, W, 3) float32 黑底图 [0, 255]
        white_img: (H, W, 3) float32 白底图 [0, 255]

    Returns:
        alpha: (H, W) uint8 alpha 通道
        foreground: (H, W, 3) uint8 前景色
    """
    diff = np.mean(white_img - black_img, axis=2)  # (H, W)
    alpha = 1.0 - diff / 255.0
    alpha = np.clip(alpha, 0.0, 1.0)

    safe_alpha = np.where(alpha > 0, alpha, 1.0)
    foreground = black_img / safe_alpha[:, :, np.newaxis]
    foreground = np.clip(foreground, 0, 255).astype(np.uint8)
    alpha = (alpha * 255).astype(np.uint8)

    return alpha, foreground


def main():
    parser = argparse.ArgumentParser(description="黑白差分去背景")
    parser.add_argument("-b", "--black", required=True, help="黑底图路径")
    parser.add_argument("-w", "--white", required=True, help="白底图路径")
    parser.add_argument("-o", "--output", help="输出路径（默认黑底图文件名 + _bwdiff.png）")
    args = parser.parse_args()

    black = Image.open(args.black).convert("RGB")
    white = Image.open(args.white).convert("RGB")

    if black.size != white.size:
        print(f"错误：两张图片尺寸不一致（黑底: {black.size}，白底: {white.size}）")
        raise SystemExit(1)

    if args.output:
        output_path = args.output
    else:
        import os
        base, _ = os.path.splitext(args.black)
        output_path = base + "_bwdiff.png"

    black_arr = np.array(black, dtype=np.float32)
    white_arr = np.array(white, dtype=np.float32)

    alpha, foreground = compute_alpha(black_arr, white_arr)

    result = np.dstack([foreground, alpha])
    result_img = Image.fromarray(result, "RGBA")
    result_img.save(output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证脚本可执行（语法检查）**

```bash
python -c "import ast; ast.parse(open('.claude/skills/rmbg/scripts/bw_diff.py').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 生成测试用图验证算法**

```bash
python -c "
import numpy as np
from PIL import Image
from .claude.skills.rmbg.scripts.bw_diff import compute_alpha

# 测试：半透明红色像素 (R=255, a=0.5)
# 黑底: Cb = 255 * 0.5 = 127.5
# 白底: Cw = 255 * 0.5 + 255 * 0.5 = 255
black = np.full((1, 1, 3), 127.5, dtype=np.float32)
white = np.full((1, 1, 3), 255.0, dtype=np.float32)
alpha, fg = compute_alpha(black, white)
print(f'Alpha: {alpha[0,0]} (expected ~128)')
print(f'Foreground R: {fg[0,0,0]} (expected ~255)')
"
```

Expected: `Alpha: ~128`, `Foreground R: ~255`

- [ ] **Step 4: 提交**

```bash
git add .claude/skills/rmbg/scripts/bw_diff.py
git commit -m "feat: add bw_diff.py script for black-white difference background removal"
```

---

### Task 2: 创建 SKILL.md

**Files:**
- Create: `.claude/skills/bwdiff/SKILL.md`

- [ ] **Step 1: 创建独立的 bwdiff 技能文档**

```markdown
---
name: bwdiff
description: 使用黑白差分算法去除图像背景...
---

# 黑白差分去背景（bwdiff）

通过黑底图和白底图的像素差值反算 alpha 通道...
```

- [ ] **Step 2: 提交**

```bash
git add .claude/skills/bwdiff/SKILL.md
git commit -m "docs: add bwdiff skill documentation"
```
