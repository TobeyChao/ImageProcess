# 色键抠图（Chroma Key）设计文档

## 动机

RMBG-2.0 深度学习去背景在处理有明显分界的图片（如纯不透明 UI 按钮、图标、纯色背景素材）时效果不佳，边缘模糊/脏。这些场景不需要 AI 去猜边界——用颜色距离即可精确计算。

## 目标场景

- 纯色背景的 UI 按钮、图标、徽标
- AI 生图时已知背景色（如指定黑色/白色背景），生图后直接抠出
- 任何主体不透明 + 背景纯色的图片

## 不适用场景（不处理）

- 复杂自然背景（请用 rmbg）
- 半透明/毛玻璃主体（不属于本方法范围）
- 背景非纯色/有纹理（请用 bwdiff 或 rmbg）

## 核心算法

泛洪填充 + 容差 + 边缘柔化，效果等同 Photoshop 魔术橡皮擦。

```
输入: PIL Image + 目标背景色 (R, G, B) + 容差 tolerance
输出: RGBA PIL Image

流程:
1. 计算每个像素与目标色的欧几里得距离
2. 距离 ≤ tolerance → 标记为"背景候选"
3. 从四边出发做泛洪填充 → 只保留连通的背景区域
   （主体上的同色像素因不连通不会被误删）
4. 边界像素按距离映射到 alpha (0-255)：
   - 距离远小于 tolerance → alpha=0（完全透明）
   - 距离接近 tolerance → alpha 线性渐变（处理抗锯齿边缘）
   - 距离 = tolerance → alpha=255（不透明）
5. 合成 RGBA 输出
```

### 关键参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| color | (R,G,B) tuple 或 "auto" | "auto" | 目标背景色，Hex 字符串或 RGB tuple 或自动检测 |
| tolerance | int (0-255) | 32 | 颜色距离阈值 |

### 自动检测背景色

从图片四角各取 5×5 像素区域，合并后取中位数颜色。适合背景色均匀分布在边缘的图。

## 用户交互

三种背景色指定方式：

1. **自动检测**（默认）：上传图片后自动执行，填入色值显示
2. **点击取色**：通过 `gr.Image.select` 事件，用户在图片上点击背景区域，取该像素颜色
3. **手动输入**：Hex 文本框（如 `#FFFFFF`），可手动修改

## 文件清单

```
.claude/skills/chroma-key/
  chroma-key.md                        # skill 定义（Markdown 描述）
  scripts/
    chroma_key.py                      # 核心脚本
    ├── auto_detect_color(image)       # 四角采样自动检测背景色
    ├── chroma_key_remove(image, color, tolerance)  # 色键抠图主函数
    └── __main__                       # CLI 入口
app.py                                 # 新增 "🌈 色键抠图" Tab
core/skills.py                         # 新增 "chroma-key" 条目
```

无新增依赖。仅使用 pillow + numpy（已在 requirements.txt 中）。

## CLI

```bash
python .claude/skills/chroma-key/scripts/chroma_key.py \
  -i <输入图片> \
  -c "#FF0000" \          # 背景色 Hex，或 "auto" 自动检测
  -t 32 \                 # 容差 0-255
  [-o <输出路径>]          # 默认输入文件名 + _chroma.png
```

## UI（Gradio Tab）

Tab 名：`🌈 色键抠图`

布局（左右两栏）：

**左栏（输入）：**
- `gr.Image` 上传图片（type="pil"，支持 `.select` 点击取色）
- `gr.Textbox` 背景色 Hex 值（可编辑）+ 色块预览
- `gr.Slider` 容差（0-255，默认 32，step=1）
- `gr.Button` "🎯 自动检测背景色"
- `gr.Button` "▶ 开始处理"（variant="primary"）

**右栏（输出）：**
- `gr.Image` 结果（format="png"，image_mode="RGBA"，棋盘格背景 CSS）
- `gr.Textbox` 状态信息

### 事件流

1. **上传图片** → 自动执行 auto_detect → 更新背景色 Textbox
2. **点击图片背景区域** → `Image.select` 返回坐标 → 取像素色 → 更新 Textbox
3. **手动修改 Hex** → 更新色块预览
4. **调整容差** → 无实时预览（避免复杂度）
5. **"自动检测"按钮** → 重新执行 auto_detect → 更新 Textbox
6. **"开始处理"** → chroma_key_remove → 输出 RGBA + 状态

## 错误处理

- 图片未上传 → "请上传图片"
- 无效的 Hex 颜色值 → "颜色格式错误，请输入如 #FF0000 的格式"
- 图片过大（> 4096×4096） → 提示可能较慢
- 其他异常 → 走 `errors.user_message()` 转中文文案

## 不做

- 不做实时预览（每调一次容差就重新计算）——计算本身很快（ms 级），但要单独加事件链路，先不做
- 不做"非连续"模式（全局删色）——泛洪填充已解决主体同色问题
- 不做渐变背景处理——保持单一容差阈值，够用即可
- 不引入 OpenCV 依赖——pillow + numpy 足够
