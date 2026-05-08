import os
import sys

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

    safe_alpha = np.where(alpha > 1e-3, alpha, 1.0)
    foreground = black_img / safe_alpha[:, :, np.newaxis]
    foreground = np.clip(foreground, 0, 255).astype(np.uint8)
    alpha = (alpha * 255).astype(np.uint8)

    return alpha, foreground


def bw_diff(black_path, white_path):
    """Run black-white difference background removal.

    Args:
        black_path: path to black-background image
        white_path: path to white-background image

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

    alpha, foreground = compute_alpha(black_arr, white_arr)

    result = np.dstack([foreground, alpha])
    return Image.fromarray(result, "RGBA")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="黑白差分去背景")
    parser.add_argument("-b", "--black", required=True, help="黑底图路径")
    parser.add_argument("-w", "--white", required=True, help="白底图路径")
    parser.add_argument("-o", "--output", help="输出路径（默认黑底图文件名 + _bwdiff.png）")
    args = parser.parse_args()

    try:
        result = bw_diff(args.black, args.white)
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