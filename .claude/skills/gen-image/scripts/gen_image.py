import os
import re
import sys
import math
import base64
import argparse
import requests
from datetime import datetime

VALID_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"}
VALID_SIZES = {"512", "1K", "2K", "4K"}
DEFAULT_RATIO = "1:1"
DEFAULT_SIZE = "1K"
DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"


def _load_config():
    config_path = os.path.join("local", "config.json")
    if os.path.isfile(config_path):
        import json
        with open(config_path) as f:
            return json.load(f)
    return {}


def _get_api_key(env_var, config_key):
    config = _load_config()
    return config.get(config_key) or os.environ.get(env_var)


def ratio_to_pixels(ratio: str, size: str) -> str:
    if ratio == "1:1":
        return size
    rw, rh = map(int, ratio.split(":"))
    size_pixels = {"512": 1024 * 1024, "1K": 1024 * 1024, "2K": 2048 * 2048, "4K": 4096 * 4096}
    target = size_pixels[size]
    w = round(math.sqrt(target * rw / rh))
    h = round(math.sqrt(target * rh / rw))
    return f"{w}*{h}"


def handle_wan_error(resp: requests.Response):
    try:
        data = resp.json()
    except ValueError:
        print(f"错误: Wan2.7 API 返回非 JSON 响应 (HTTP {resp.status_code})", file=sys.stderr)
        return
    code = data.get("code", "")
    message = data.get("message", "")
    if code in ("InvalidApiKey", "InvalidParameter"):
        print(f"错误: API 密钥无效或参数错误 - {message}", file=sys.stderr)
    elif code == "Throttling":
        print(f"错误: API 请求过于频繁，请稍后重试 - {message}", file=sys.stderr)
    else:
        print(f"错误: Wan2.7 API 调用失败 (HTTP {resp.status_code}) - {code}: {message}", file=sys.stderr)


# ── Gemini backend ──
def generate_gemini(prompt: str, ratio: str, size: str, output_dir: str) -> str:
    from google import genai
    from google.genai import types

    api_key = _get_api_key("GEMINI_API_KEY", "gemini_api_key")
    if not api_key:
        raise RuntimeError("未设置 Gemini API Key，请在设置页或 GEMINI_API_KEY 环境变量中配置")

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio=ratio,
            image_size=size
        ),
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[prompt],
        config=config
    )

    caption = ""
    saved = False
    filepath = ""
    for part in response.parts:
        if part.text is not None:
            caption = part.text.strip()
            print(caption)
        elif part.inline_data is not None:
            image = part.as_image()
            slug = re.sub(r"[^\w一-鿿]+", "_", caption)[:40].strip("_") if caption else "generated"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{slug}_{timestamp}.png"
            filepath = os.path.join(output_dir, filename)
            image.save(filepath)
            saved = True

    if not saved:
        raise RuntimeError("Gemini API 未返回图片，可能被安全过滤器拦截")
    return filepath


# ── Wan2.7 backend ──
def generate_wan(prompt: str, ratio: str, size: str, output_dir: str) -> str:
    api_key = _get_api_key("DASHSCOPE_API_KEY", "dashscope_api_key")
    if not api_key:
        raise RuntimeError("未设置 DashScope API Key，请在设置页或 DASHSCOPE_API_KEY 环境变量中配置")

    pixel_size = ratio_to_pixels(ratio, size)
    payload = {
        "model": "wan2.7-image-pro",
        "input": {
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ]
        },
        "parameters": {
            "size": pixel_size,
            "n": 1,
            "watermark": False
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        resp = requests.post(DASHSCOPE_URL, json=payload, headers=headers, timeout=120)
    except requests.RequestException as e:
        raise RuntimeError(f"网络请求失败 - {e}")

    if resp.status_code != 200:
        handle_wan_error(resp)
        raise RuntimeError("Wan2.7 API 调用失败")

    data = resp.json()
    choices = data.get("output", {}).get("choices", [])
    if not choices:
        raise RuntimeError("Wan2.7 API 未返回图片")

    saved = []
    for choice in choices:
        for content in choice.get("message", {}).get("content", []):
            if content.get("type") == "image":
                image_url = content["image"]
                try:
                    img_resp = requests.get(image_url, timeout=60)
                    img_resp.raise_for_status()
                except requests.RequestException as e:
                    raise RuntimeError(f"下载图片失败 - {e}")

                slug = re.sub(r"[^\w一-鿿]+", "_", prompt)[:40].strip("_")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{slug}_{timestamp}.png"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(img_resp.content)
                saved.append(filepath)

    if not saved:
        raise RuntimeError("Wan2.7 API 未返回图片")
    return saved[0]


def generate_image(prompt: str, ratio: str = DEFAULT_RATIO, size: str = DEFAULT_SIZE,
                   output_dir: str = "local/output", model: str = "gemini"):
    """Generate an image from text description.

    Returns:
        File path of the generated image
    """
    os.makedirs(output_dir, exist_ok=True)

    if model == "wan":
        return generate_wan(prompt, ratio, size, output_dir)
    else:
        return generate_gemini(prompt, ratio, size, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="使用 Gemini 或 Wan2.7 生成图像")
    parser.add_argument("-p", "--prompt", required=True, help="图像生成提示词")
    parser.add_argument("-r", "--ratio", default=DEFAULT_RATIO, help=f"宽高比（默认 {DEFAULT_RATIO}）")
    parser.add_argument("-s", "--size", default=DEFAULT_SIZE, help=f"分辨率：512, 1K, 2K, 4K（默认 {DEFAULT_SIZE}）")
    parser.add_argument("-o", "--output", default="local/output", help="输出目录（默认 local/output）")
    parser.add_argument("-m", "--model", default="gemini", choices=["gemini", "wan"], help="模型后端")
    args = parser.parse_args()

    if args.ratio not in VALID_RATIOS:
        sys.exit(f"错误: 不支持的宽高比 '{args.ratio}'")
    if args.size not in VALID_SIZES:
        sys.exit(f"错误: 不支持的分辨率 '{args.size}'")

    try:
        filepath = generate_image(args.prompt, args.ratio, args.size, args.output, args.model)
        print(f"图片已保存: {filepath}")
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)