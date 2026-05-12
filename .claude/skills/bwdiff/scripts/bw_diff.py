import os
import sys

import numpy as np
from PIL import Image


def compute_alpha(black_img, white_img, tolerance=10):
    """逐像素计算 alpha 通道和前景色。

    Args:
        black_img: (H, W, 3) float32 黑底图 [0, 255]
        white_img: (H, W, 3) float32 白底图 [0, 255]
        tolerance: 背景容差 0-100，容忍 AI 生成图背景不是纯黑/纯白的误差。
                   diff >= 255-tolerance 的像素视为纯背景（alpha=0），
                   diff <= tolerance 的像素视为纯前景（alpha=1），中间线性插值。

    Returns:
        alpha: (H, W) uint8 alpha 通道
        foreground: (H, W, 3) uint8 前景色（透明像素的 RGB 已清零）
    """
    diff = np.mean(white_img - black_img, axis=2)  # (H, W), range [0, 255]

    t = float(np.clip(tolerance, 0, 100))
    low, high = t, 255.0 - t
    if high > low:
        diff_mapped = (diff - low) / (high - low)
    else:
        # tolerance 过大时退化为硬阈值
        diff_mapped = np.where(diff >= 127.5, 1.0, 0.0)
    alpha = 1.0 - np.clip(diff_mapped, 0.0, 1.0)

    safe_alpha = np.where(alpha > 1e-3, alpha, 1.0)
    foreground = black_img / safe_alpha[:, :, np.newaxis]
    foreground = np.clip(foreground, 0, 255).astype(np.uint8)

    # 透明像素的 RGB 通道清零，避免 AI 生图在透明区域产生的杂乱色值污染合成结果
    foreground[alpha < (1.0 / 255.0)] = 0

    alpha = (alpha * 255).astype(np.uint8)
    return alpha, foreground


def bw_diff(black_path, white_path, tolerance=10):
    """Run black-white difference background removal.

    Args:
        black_path: path to black-background image
        white_path: path to white-background image
        tolerance: background noise tolerance 0-100 (default 10)

    Returns:
        PIL.Image in RGBA mode with computed alpha channel

    Raises:
        ValueError: if images have different dimensions
    """
    black = Image.open(black_path).convert("RGB")
    white = Image.open(white_path).convert("RGB")

    if black.size != white.size:
        raise ValueError(f"两张图片尺寸不一致（黑底: {black.size}，白底: {white.size}）")

    black_arr = np.array(black, dtype=np.float32)
    white_arr = np.array(white, dtype=np.float32)

    alpha, foreground = compute_alpha(black_arr, white_arr, tolerance=tolerance)

    result = np.dstack([foreground, alpha])
    return Image.fromarray(result, "RGBA")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="黑白差分去背景")
    parser.add_argument("-b", "--black", required=True, help="黑底图路径")
    parser.add_argument("-w", "--white", required=True, help="白底图路径")
    parser.add_argument("-o", "--output", help="输出路径（默认黑底图文件名 + _bwdiff.png）")
    parser.add_argument("-t", "--tolerance", type=int, default=10,
                        help="背景容差 0-100，容忍 AI 生图背景非纯黑/白的误差（默认 10）")
    args = parser.parse_args()

    try:
        result = bw_diff(args.black, args.white, tolerance=args.tolerance)
    except Exception as e:
        print(f"错误：{e}")
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        base, _ = os.path.splitext(args.black)
        output_path = base + "_bwdiff.png"

    result.save(output_path)
    print(f"Saved: {output_path}")