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
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        raise ValueError(f"无效的颜色格式: {hex_str!r}，请使用 #RRGGBB 格式")


def auto_detect_color(image: Image.Image) -> tuple:
    """从图片四角各取 5x5 像素，合并后取中位数颜色。返回 (R, G, B)。"""
    img = image.convert("RGB")
    w, h = img.size
    samples = []
    corners = [(0, 0), (w - 5, 0), (0, h - 5), (w - 5, h - 5)]
    for x, y in corners:
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        x2 = min(x + 5, w)
        y2 = min(y + 5, h)
        crop = img.crop((x, y, x2, y2))
        samples.append(np.array(crop, dtype=np.uint8).reshape(-1, 3))
    all_pixels = np.vstack(samples)
    median = np.median(all_pixels, axis=0).astype(np.uint8)
    return tuple(int(c) for c in median)


def chroma_key_remove(image: Image.Image, color: str | tuple, tolerance: int = 32) -> Image.Image:
    """色键抠图，返回 RGBA PIL Image。

    Args:
        image: PIL RGB Image
        color: (R, G, B) tuple 或 "auto" 字符串
        tolerance: 容差 0-255
    """
    tolerance = max(1, min(255, int(tolerance)))

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
    if tolerance > 0:
        t = np.clip(d / tolerance, 0.0, 1.0)
        alpha[in_region] = (t * 255).astype(np.uint8)
    else:
        alpha[in_region] = 0

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
