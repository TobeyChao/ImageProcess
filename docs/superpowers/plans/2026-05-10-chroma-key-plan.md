# 色键抠图（Chroma Key）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增色键抠图功能——通过泛洪填充+容差+边缘柔化算法移除纯色背景，输出 RGBA 透明 PNG。

**Architecture:** 新增 `.claude/skills/chroma-key/` 技能目录，核心逻辑放在 `scripts/chroma_key.py`（纯 pillow+numpy，无额外依赖）。在 `core/skills.py` 注册，在 `app.py` 新增独立顶层 Tab。

**Tech Stack:** Python ≥ 3.10, pillow, numpy, gradio

---

### Task 1: 创建 skill 目录和定义文件

**Files:**
- Create: `.claude/skills/chroma-key/chroma-key.md`
- Create: `.claude/skills/chroma-key/scripts/` (directory)

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p .claude/skills/chroma-key/scripts
```

- [ ] **Step 2: 编写 chroma-key.md skill 定义**

```markdown
# Chroma Key 色键抠图

通过泛洪填充+容差+边缘柔化算法移除纯色背景，效果等同 Photoshop 魔术橡皮擦。

## 适用场景
- 纯色背景的 UI 按钮、图标、徽标
- AI 生图时已知背景色，生图后直接抠出
- 任何主体不透明 + 背景纯色的图片

## 用法

```bash
python .claude/skills/chroma-key/scripts/chroma_key.py \
  -i <输入图片> \
  -c "#FF0000" \          # 背景色 Hex，或 "auto" 自动检测
  -t 32 \                 # 容差 0-255
  [-o <输出路径>]          # 默认输入文件名 + _chroma.png
```

## 算法
1. 计算每个像素与目标色的欧几里得距离
2. 距离 ≤ 容差 → 背景候选
3. 从四边泛洪填充 → 只保留连通的背景区域
4. 边界像素按距离映射 alpha（线性渐变，处理抗锯齿）
5. 合成 RGBA 输出

## 依赖
pillow, numpy（无 GPU 要求）
```

- [ ] **Step 3: 提交**

```bash
git add .claude/skills/chroma-key/
git commit -m "feat: add chroma-key skill definition"
```

---

### Task 2: 编写核心脚本 chroma_key.py

**Files:**
- Create: `.claude/skills/chroma-key/scripts/chroma_key.py`

- [ ] **Step 1: 编写脚本完整代码**

```python
import os
import sys
import numpy as np
from PIL import Image


def parse_hex_color(hex_str: str) -> tuple:
    """Parse '#RRGGBB' or '#RGB' hex string to (R, G, B) tuple."""
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        raise ValueError(f"无效的颜色格式: {hex_str!r}，请使用 #RRGGBB 格式")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def auto_detect_color(image: Image.Image) -> tuple:
    """从图片四角各取 5x5 像素，合并后取中位数颜色。返回 (R, G, B)。"""
    img = image.convert("RGB")
    w, h = img.size
    samples = []
    corners = [(0, 0), (w - 5, 0), (0, h - 5), (w - 5, h - 5)]
    for x, y in corners:
        x = max(0, min(x, w - 5))
        y = max(0, min(y, h - 5))
        crop = img.crop((x, y, x + 5, y + 5))
        samples.append(np.array(crop, dtype=np.uint8).reshape(-1, 3))
    all_pixels = np.vstack(samples)
    median = np.median(all_pixels, axis=0).astype(np.uint8)
    return tuple(int(c) for c in median)


def chroma_key_remove(image: Image.Image, color, tolerance: int = 32) -> Image.Image:
    """色键抠图，返回 RGBA PIL Image。

    Args:
        image: PIL RGB Image
        color: (R, G, B) tuple 或 "auto" 字符串
        tolerance: 容差 0-255
    """
    if isinstance(color, str) and color.lower() == "auto":
        color = auto_detect_color(image)
    elif isinstance(color, str):
        color = parse_hex_color(color)

    img = image.convert("RGB")
    arr = np.array(img, dtype=np.float32)  # (H, W, 3)

    # 1. 计算欧几里得距离
    target = np.array(color, dtype=np.float32)
    diff = arr - target[np.newaxis, np.newaxis, :]
    distance = np.sqrt(np.sum(diff ** 2, axis=2))  # (H, W)

    # 2. 背景候选 mask（距离 ≤ 容差）
    candidate = distance <= tolerance  # (H, W) bool

    # 3. 从四边出发泛洪填充
    h, w = candidate.shape
    visited = np.zeros((h, w), dtype=bool)
    queue = []

    # 初始化：四边上的背景候选像素
    for y in range(h):
        if candidate[y, 0]:
            queue.append((y, 0))
            visited[y, 0] = True
        if w > 1 and candidate[y, w - 1]:
            queue.append((y, w - 1))
            visited[y, w - 1] = True
    for x in range(1, w - 1):
        if candidate[0, x]:
            queue.append((0, x))
            visited[0, x] = True
        if h > 1 and candidate[h - 1, x]:
            queue.append((h - 1, x))
            visited[h - 1, x] = True

    # BFS（4 连通）
    head = 0
    while head < len(queue):
        y, x = queue[head]
        head += 1
        for ny, nx in [(y-1, x), (y+1, x), (y, x-1), (y, x+1)]:
            if 0 <= ny < h and 0 <= nx < w:
                if candidate[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx))

    # 4. 计算 alpha 通道
    # 在 flood fill 区域内，alpha 根据距离线性映射
    # distance=0 → alpha=0（完全透明）
    # distance=tolerance → alpha=255（不透明）
    alpha = np.full((h, w), 255, dtype=np.uint8)
    in_region = visited
    d = distance[in_region]
    t = np.clip(d / tolerance, 0.0, 1.0)  # 0.0 (far from bg) to 1.0 (close to bg)
    # 反转：distance 小 → alpha 小（透明）
    alpha[in_region] = (t * 255).astype(np.uint8)

    # 5. 合成 RGBA
    result = np.dstack([arr.astype(np.uint8), alpha])
    return Image.fromarray(result, "RGBA")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="色键抠图——移除纯色背景")
    parser.add_argument("-i", "--input", required=True, help="输入图片路径")
    parser.add_argument("-c", "--color", default="auto", help="背景色 Hex（如 #FF0000）或 'auto' 自动检测")
    parser.add_argument("-t", "--tolerance", type=int, default=32, help="容差 0-255（默认 32）")
    parser.add_argument("-o", "--output", help="输出路径（默认输入文件名 + _chroma.png）")
    args = parser.parse_args()

    try:
        image = Image.open(args.input).convert("RGB")
    except Exception:
        sys.exit(f"无法打开图片: {args.input}")

    try:
        result = chroma_key_remove(image, args.color, args.tolerance)
    except Exception as e:
        sys.exit(f"处理失败: {e}")

    if args.output:
        output_path = args.output
    else:
        base, _ = os.path.splitext(args.input)
        output_path = base + "_chroma.png"

    result.save(output_path)
    print(f"Saved: {output_path}")
```

- [ ] **Step 2: 验证脚本语法正确**

```bash
python -c "from pathlib import Path; import sys; sys.path.insert(0, '.claude/skills/chroma-key/scripts'); import chroma_key; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add .claude/skills/chroma-key/scripts/chroma_key.py
git commit -m "feat: add chroma_key core script (flood fill + tolerance + edge softening)"
```

---

### Task 3: 在 core/skills.py 中注册新技能

**Files:**
- Modify: `core/skills.py:14-19`

- [ ] **Step 1: 添加 chroma-key 条目**

在 `SKILL_SCRIPTS` 字典中添加：

```python
    "chroma-key": ("chroma-key/scripts/chroma_key.py", "chroma_key"),
```

插入位置在 `"bwdiff"` 后面：

```python
SKILL_SCRIPTS: dict[str, tuple[str, str]] = {
    "rmbg": ("rmbg/scripts/rmbg_process.py", "rmbg_process"),
    "bwdiff": ("bwdiff/scripts/bw_diff.py", "bw_diff"),
    "chroma-key": ("chroma-key/scripts/chroma_key.py", "chroma_key"),
    "bwgen": ("bwgen/scripts/bw_gen.py", "bw_gen"),
    "gen-image": ("gen-image/scripts/gen_image.py", "gen_image"),
}
```

- [ ] **Step 2: 验证加载**

```bash
python -c "from core import skills; m = skills.load('chroma-key'); print(hasattr(m, 'chroma_key_remove'))"
```

Expected: `True`

- [ ] **Step 3: 提交**

```bash
git add core/skills.py
git commit -m "feat: register chroma-key skill in loader"
```

---

### Task 4: 在 app.py 中新增 Tab

**Files:**
- Modify: `app.py`

- [ ] **Step 1: 加载 chroma-key 模块**

在 `app.py` 第 22 行附近，bwdiff_mod 之后添加：

```python
chroma_mod = skills.load("chroma-key")
```

- [ ] **Step 2: 添加 chroma_key_process 函数**

在 `app.py` 中 `bwdiff_process` 函数之后（约第 268 行后），新增：

```python
# ── Tab: Chroma Key ────────────────────────────────────────────────────────────

def _hex_to_rgb_textbox_update(hex_val):
    """Return a gr.update for the color preview. Does NOT validate format here."""
    return hex_val


def chroma_auto_detect(image):
    """Auto-detect background color from uploaded image."""
    if image is None:
        return "", "请先上传图片"
    try:
        r, g, b = chroma_mod.auto_detect_color(image)
        return f"#{r:02X}{g:02X}{b:02X}", ""
    except Exception as e:
        msg, hint = errors.user_message(e)
        return "", f"{msg}\n{hint}"


def chroma_pick_color(image, evt: gr.SelectData):
    """Handle click-to-pick on image."""
    if image is None:
        return "", "请先上传图片"
    try:
        x, y = evt.index[0], evt.index[1]
        rgb = image.convert("RGB")
        r, g, b = rgb.getpixel((x, y))
        return f"#{r:02X}{g:02X}{b:02X}", ""
    except Exception as e:
        msg, hint = errors.user_message(e)
        return "", f"{msg}\n{hint}"


def chroma_key_process(image, color_hex, tolerance):
    """Main processing function for chroma key tab."""
    if image is None:
        return None, "请上传图片"
    if not color_hex or not color_hex.strip():
        return None, "请指定背景色或使用自动检测"
    try:
        result = chroma_mod.chroma_key_remove(
            image, color_hex.strip(), tolerance=int(tolerance)
        )
        return result, "处理完成 ✓"
    except Exception as e:
        msg, hint = errors.user_message(e)
        return None, f"{msg}\n{hint}"
```

- [ ] **Step 3: 添加 UI Tab**

在 "⬛⬜ 黑白差分" Tab 之后（约第 562 行 `bwdiff_btn.click(...)` 之后），新增：

```python
    with gr.Tab("🌈 色键抠图"):
        gr.Markdown("### 色键抠图——移除纯色背景")
        with gr.Row():
            with gr.Column(scale=1):
                chroma_input = gr.Image(label="上传图片", type="pil", height="45vh")
                with gr.Row():
                    chroma_color = gr.Textbox(
                        label="背景色", placeholder="#FFFFFF（自动检测或手动输入）",
                        scale=3,
                    )
                with gr.Row():
                    chroma_auto_btn = gr.Button("🎯 自动检测", size="sm", scale=1)
                chroma_tolerance = gr.Slider(
                    label="容差", minimum=1, maximum=255, value=32, step=1,
                    info="值越大，抠除的颜色范围越宽",
                )
                chroma_btn = gr.Button("▶ 开始处理", variant="primary", size="lg")
            with gr.Column(scale=1):
                chroma_output = gr.Image(label="结果", type="pil", height="45vh",
                                        format="png", image_mode="RGBA", buttons=["fullscreen"],
                                        elem_classes=["alpha-preview"])
                chroma_status = gr.Textbox(label="状态", interactive=False, lines=1)
        chroma_msg_state = gr.State("")

        # 上传图片 → 自动检测背景色
        chroma_input.upload(
            fn=chroma_auto_detect,
            inputs=[chroma_input],
            outputs=[chroma_color, chroma_status],
        )

        # 点击图片取色
        chroma_input.select(
            fn=chroma_pick_color,
            inputs=[chroma_input],
            outputs=[chroma_color, chroma_status],
        )

        # 自动检测按钮
        chroma_auto_btn.click(
            fn=chroma_auto_detect,
            inputs=[chroma_input],
            outputs=[chroma_color, chroma_status],
        )

        # 开始处理
        chroma_btn.click(
            fn=lambda: "处理中...",
            outputs=[chroma_status],
        ).then(
            fn=chroma_key_process,
            inputs=[chroma_input, chroma_color, chroma_tolerance],
            outputs=[chroma_output, chroma_msg_state],
        ).then(
            fn=lambda s: s,
            inputs=[chroma_msg_state],
            outputs=[chroma_status],
        )
```

- [ ] **Step 4: 添加 output 目录创建**

在 `app.py` 最底部 `__main__` 中（约第 699 行），`for sub in [...]` 列表中添加 `"chroma-key"`：

```python
    for sub in ["rmbg", "bwdiff", "bwgen", "gen-image", "chroma-key"]:
```

- [ ] **Step 5: 验证 app.py 语法正确**

```bash
python -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 6: 提交**

```bash
git add app.py
git commit -m "feat(ui): add chroma key tab with auto-detect, click-to-pick, and tolerance control"
```

---

### Task 5: 更新 tests/test_skills.py

**Files:**
- Modify: `tests/test_skills.py:30-33`

- [ ] **Step 1: 添加 chroma-key 到已知技能列表测试**

修改 `test_all_known_skills_loadable`：

```python
def test_all_known_skills_loadable():
    for name in ["rmbg", "bwdiff", "chroma-key", "bwgen", "gen-image"]:
        mod = skills.load(name)
        assert mod is not None
```

同时添加一个针对 chroma-key 模块的导入测试：

```python
def test_chroma_key_has_expected_functions():
    mod = skills.load("chroma-key")
    assert hasattr(mod, "chroma_key_remove")
    assert hasattr(mod, "auto_detect_color")
    assert hasattr(mod, "parse_hex_color")
```

- [ ] **Step 2: 运行测试验证**

```bash
pytest tests/test_skills.py -v
```

Expected: 5 passed (4 existing + 1 new)

- [ ] **Step 3: 提交**

```bash
git add tests/test_skills.py
git commit -m "test: add chroma-key to skill loader tests"
```

---

### Task 6: 编写 chroma_key 核心逻辑单元测试

**Files:**
- Create: `tests/test_chroma_key.py`

- [ ] **Step 1: 编写测试文件**

```python
"""Tests for chroma key background removal."""
import numpy as np
import pytest
from PIL import Image

# Import the skill module
from core import skills

chroma_key = skills.load("chroma-key")


class TestParseHexColor:
    def test_standard_hex(self):
        assert chroma_key.parse_hex_color("#FF0000") == (255, 0, 0)
        assert chroma_key.parse_hex_color("#00FF00") == (0, 255, 0)
        assert chroma_key.parse_hex_color("#0000FF") == (0, 0, 255)
        assert chroma_key.parse_hex_color("#FFFFFF") == (255, 255, 255)
        assert chroma_key.parse_hex_color("#000000") == (0, 0, 0)

    def test_hex_without_hash(self):
        assert chroma_key.parse_hex_color("FF0000") == (255, 0, 0)

    def test_short_hex(self):
        assert chroma_key.parse_hex_color("#F00") == (255, 0, 0)
        assert chroma_key.parse_hex_color("#FFF") == (255, 255, 255)
        assert chroma_key.parse_hex_color("000") == (0, 0, 0)

    def test_invalid_hex_raises(self):
        with pytest.raises(ValueError):
            chroma_key.parse_hex_color("not a color")
        with pytest.raises(ValueError):
            chroma_key.parse_hex_color("#GGGGGG")


class TestAutoDetectColor:
    def test_solid_color_image(self):
        """An image with a single solid color should detect that color."""
        img = Image.new("RGB", (100, 100), (128, 64, 200))
        color = chroma_key.auto_detect_color(img)
        assert color == (128, 64, 200)

    def test_image_with_corners_same_color(self):
        """Image where corners share the same background color."""
        img = Image.new("RGB", (200, 200), (0, 255, 0))
        # Draw a non-background rectangle in center
        arr = np.array(img)
        arr[50:150, 50:150] = (255, 0, 0)
        img = Image.fromarray(arr)
        color = chroma_key.auto_detect_color(img)
        assert color == (0, 255, 0)


class TestChromaKeyRemove:
    def test_solid_background_fully_removed(self):
        """Pure red image on pure blue background: all blue pixels become transparent."""
        img = Image.new("RGB", (50, 50), (0, 0, 255))  # blue background
        arr = np.array(img)
        # Red rectangle in center (NOT touching any edge)
        arr[10:40, 10:40] = (255, 0, 0)
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (0, 0, 255), tolerance=10)

        # Center pixel (red, foreground) should be opaque
        r, g, b, a = result.getpixel((25, 25))
        assert a == 255
        assert (r, g, b) == (255, 0, 0)

        # Edge pixel (blue, background) should be transparent
        r, g, b, a = result.getpixel((0, 0))
        assert a == 0

    def test_foreground_same_color_as_background_preserved(self):
        """Foreground has same color as background but not connected to edge."""
        img = Image.new("RGB", (50, 50), (0, 255, 0))  # green bg
        arr = np.array(img)
        # Red shape touching edges → will be flood-filled
        arr[0:10, :] = (255, 0, 0)
        arr[40:50, :] = (255, 0, 0)
        arr[:, 0:10] = (255, 0, 0)
        arr[:, 40:50] = (255, 0, 0)
        # Isolated green block in center (same green as bg, but not connected)
        arr[20:30, 20:30] = (0, 255, 0)
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (0, 255, 0), tolerance=10)

        # The isolated green block should be opaque (not connected to edge)
        _, _, _, a = result.getpixel((25, 25))
        assert a == 255

    def test_tolerance_affects_result(self):
        """Higher tolerance removes more pixels."""
        img = Image.new("RGB", (50, 50), (100, 100, 100))
        arr = np.array(img)
        arr[10:40, 10:40] = (128, 128, 128)  # close to background but not identical
        img = Image.fromarray(arr)

        # Low tolerance won't reach the close-color pixels
        result_low = chroma_key.chroma_key_remove(img, (100, 100, 100), tolerance=10)
        # Higher tolerance will include them via flood fill
        result_high = chroma_key.chroma_key_remove(img, (100, 100, 100), tolerance=40)

        # Count transparent pixels (alpha == 0)
        alpha_low = np.array(result_low)[:, :, 3]
        alpha_high = np.array(result_high)[:, :, 3]
        assert (alpha_high == 0).sum() > (alpha_low == 0).sum()

    def test_white_background_common_case(self):
        """Common use case: white background UI element."""
        # White background with blue button
        img = Image.new("RGB", (100, 60), (255, 255, 255))
        arr = np.array(img)
        arr[15:45, 20:80] = (70, 130, 250)  # blue button
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (255, 255, 255), tolerance=20)

        # Button center should be fully opaque
        _, _, _, a_btn = result.getpixel((50, 30))
        assert a_btn == 255

        # Corner should be fully transparent
        _, _, _, a_corner = result.getpixel((0, 0))
        assert a_corner == 0

    def test_auto_color_detection(self):
        """Pass 'auto' as color should auto-detect background."""
        img = Image.new("RGB", (50, 50), (0, 255, 0))
        arr = np.array(img)
        arr[10:40, 10:40] = (255, 0, 0)
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, "auto", tolerance=10)

        _, _, _, a = result.getpixel((25, 25))
        assert a == 255  # foreground preserved
        _, _, _, a = result.getpixel((0, 0))
        assert a == 0  # background removed

    def test_output_is_rgba(self):
        img = Image.new("RGB", (20, 20), (255, 0, 0))
        result = chroma_key.chroma_key_remove(img, (255, 0, 0), tolerance=10)
        assert result.mode == "RGBA"

    def test_image_with_no_edges_to_flood(self):
        """Image where the target color only exists in isolated center region (not touching edges)."""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        arr = np.array(img)
        arr[20:30, 20:30] = (255, 0, 0)  # red square NOT touching edges
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (255, 0, 0), tolerance=10)

        # Red is not connected to edges, so it should all remain opaque
        _, _, _, a = result.getpixel((25, 25))
        assert a == 255
```

- [ ] **Step 2: 运行全部新测试**

```bash
pytest tests/test_chroma_key.py -v
```

Expected: All tests pass.

- [ ] **Step 3: 提交**

```bash
git add tests/test_chroma_key.py
git commit -m "test: add chroma_key unit tests (parse, auto-detect, flood fill, tolerance, edge cases)"
```

---

### Task 7: 端到端验证

- [ ] **Step 1: CLI 测试（生成测试图片）**

```bash
python -c "
from PIL import Image
import numpy as np
# White bg + blue rectangle
img = Image.new('RGB', (200, 100), (255, 255, 255))
arr = np.array(img)
arr[20:80, 30:170] = (70, 130, 250)
img = Image.fromarray(arr)
img.save('/tmp/test_chroma.png')
print('Test image saved')
"

python .claude/skills/chroma-key/scripts/chroma_key.py \
  -i /tmp/test_chroma.png \
  -c "#FFFFFF" \
  -t 20 \
  -o /tmp/test_chroma_result.png
```

- [ ] **Step 2: 验证输出**

```bash
python -c "
from PIL import Image
img = Image.open('/tmp/test_chroma_result.png')
assert img.mode == 'RGBA', f'Expected RGBA, got {img.mode}'
# Corner should be transparent
_, _, _, a = img.getpixel((0, 0))
assert a == 0, f'Corner alpha should be 0, got {a}'
# Center should be opaque
_, _, _, a = img.getpixel((100, 50))
assert a == 255, f'Center alpha should be 255, got {a}'
print('Output validated OK')
"
```

Expected: `Output validated OK`

- [ ] **Step 3: 运行全部测试确保无回归**

```bash
pytest tests/ -v
```

Expected: All tests pass (existing + new).

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: chroma key background removal — flood fill + tolerance + edge softening"
```
