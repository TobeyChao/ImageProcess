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
    """Load config from local/config.json if exists."""
    config_path = os.path.join("local", "config.json")
    if os.path.isfile(config_path):
        import json
        with open(config_path) as f:
            return json.load(f)
    return {}


def _get_api_key(env_var, config_key):
    """Get API key with priority: config.json > environment variable."""
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


def handle_wan_error(resp: requests.Response, step: str = ""):
    try:
        data = resp.json()
    except ValueError:
        print(f"错误 ({step}): Wan2.7 API 返回非 JSON 响应 (HTTP {resp.status_code})", file=sys.stderr)
        return
    code = data.get("code", "")
    message = data.get("message", "")
    if code in ("InvalidApiKey", "InvalidParameter"):
        print(f"错误 ({step}): API 密钥无效或参数错误 - {message}", file=sys.stderr)
        print("请检查 DASHSCOPE_API_KEY 是否正确", file=sys.stderr)
    elif code == "Throttling":
        print(f"错误 ({step}): API 请求过于频繁，请稍后重试 - {message}", file=sys.stderr)
    else:
        print(f"错误 ({step}): Wan2.7 API 调用失败 (HTTP {resp.status_code}) - {code}: {message}", file=sys.stderr)


def download_wan_image(image_url: str, filepath: str):
    try:
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
    except requests.RequestException as e:
        print(f"错误: 下载图片失败 - {e}", file=sys.stderr)
        sys.exit(1)
    with open(filepath, "wb") as f:
        f.write(img_resp.content)


def _slug_from_prompt(prompt: str) -> str:
    return re.sub(r"[^\w一-鿿]+", "_", prompt)[:40].strip("_")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── Gemini backend ──
def bwgen_gemini(prompt: str, ratio: str, size: str, output_dir: str):
    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError, ServerError, APIError

    api_key = _get_api_key("GEMINI_API_KEY", "gemini_api_key")
    if not api_key:
        raise RuntimeError("未设置 Gemini API Key，请在设置页或 GEMINI_API_KEY 环境变量中配置")

    client = genai.Client(api_key=api_key)

    def handle_api_error(e: APIError, step: str) -> None:
        code = getattr(e, "code", None)
        if code == 401 or code == 403:
            print(f"错误 ({step}): API 密钥无效或无权访问", file=sys.stderr)
        elif code == 429:
            print(f"错误 ({step}): API 配额用尽或请求过于频繁", file=sys.stderr)
        elif code == 400:
            msg = str(e).lower()
            if "location" in msg or "region" in msg:
                print(f"错误 ({step}): 当前地区不支持 Gemini 图片生成", file=sys.stderr)
            elif "safety" in msg:
                print(f"错误 ({step}): 内容被安全过滤器拦截，请修改提示词后重试", file=sys.stderr)
            else:
                print(f"错误 ({step}): 请求参数无效 - {e}", file=sys.stderr)
        elif code and 500 <= code < 600:
            print(f"错误 ({step}): Gemini 服务器错误 (HTTP {code})，请稍后重试", file=sys.stderr)
        else:
            print(f"错误 ({step}): API 调用失败 - {e}", file=sys.stderr)

    try:
        chat = client.chats.create(
            model="gemini-2.5-flash-image",
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=ratio,
                    image_size=size,
                ),
            )
        )
    except ClientError as e:
        handle_api_error(e, "初始化会话")
        raise
    except ServerError as e:
        handle_api_error(e, "初始化会话")
        raise

    slug = _slug_from_prompt(prompt)
    ts = _timestamp()

    # Step 1: generate with black background
    print("Step 1/2: 生成黑底图...")
    step1_prompt = f"{prompt}, pure black background #000000 solid background, do not add any elements beyond the described subject, no shadows, no reflections, no ground plane, no environment"

    try:
        step1_response = chat.send_message(step1_prompt)
    except (ClientError, ServerError) as e:
        handle_api_error(e, "Step 1")
        raise

    if step1_response.parts is None:
        raise RuntimeError("错误 (Step 1): API 返回空响应，可能被安全过滤器拦截")

    black_path = os.path.join(output_dir, f"{slug}_{ts}_black.png")
    black_saved = False
    for part in step1_response.parts:
        if part.inline_data is not None:
            part.as_image().save(black_path)
            black_saved = True

    if not black_saved:
        raise RuntimeError("错误 (Step 1): API 未返回图片")

    # Step 2: edit image, black → white background
    print("Step 2/2: 背景换白...")
    step2_prompt = "Change the background from black to pure white #FFFFFF. Keep the subject, lighting, details, and position exactly the same. Do not change anything except the background color."

    try:
        step2_response = chat.send_message(step2_prompt)
    except (ClientError, ServerError) as e:
        handle_api_error(e, "Step 2")
        raise

    if step2_response.parts is None:
        raise RuntimeError("错误 (Step 2): API 返回空响应")

    white_path = os.path.join(output_dir, f"{slug}_{ts}_white.png")
    white_saved = False
    for part in step2_response.parts:
        if part.inline_data is not None:
            part.as_image().save(white_path)
            white_saved = True

    if not white_saved:
        raise RuntimeError("错误 (Step 2): API 未返回图片")

    return black_path, white_path


# ── Wan2.7 backend ──
def bwgen_wan(prompt: str, ratio: str, size: str, output_dir: str):
    api_key = _get_api_key("DASHSCOPE_API_KEY", "dashscope_api_key")
    if not api_key:
        raise RuntimeError("未设置 DashScope API Key，请在设置页或 DASHSCOPE_API_KEY 环境变量中配置")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    pixel_size = ratio_to_pixels(ratio, size)
    slug = _slug_from_prompt(prompt)
    ts = _timestamp()

    # Step 1: text-to-image with black background
    print("Step 1/2: 生成黑底图 (Wan2.7)...")
    step1_prompt = f"{prompt}, pure black background #000000 solid background, do not add any elements beyond the described subject, no shadows, no reflections, no ground plane, no environment"

    payload = {
        "model": "wan2.7-image-pro",
        "input": {
            "messages": [
                {"role": "user", "content": [{"text": step1_prompt}]}
            ]
        },
        "parameters": {
            "size": pixel_size,
            "n": 1,
            "watermark": False
        }
    }

    try:
        resp = requests.post(DASHSCOPE_URL, json=payload, headers=headers, timeout=120)
    except requests.RequestException as e:
        raise RuntimeError(f"网络请求失败 - {e}")

    if resp.status_code != 200:
        handle_wan_error(resp, "Step 1")
        raise RuntimeError("Wan2.7 API 调用失败")

    data = resp.json()
    choices = data.get("output", {}).get("choices", [])
    if not choices:
        raise RuntimeError("错误 (Step 1): Wan2.7 API 未返回图片")

    black_path = os.path.join(output_dir, f"{slug}_{ts}_black.png")
    black_saved = False
    for choice in choices:
        for content in choice.get("message", {}).get("content", []):
            if content.get("type") == "image":
                download_wan_image(content["image"], black_path)
                print(f"  -> {black_path}")
                black_saved = True

    if not black_saved:
        raise RuntimeError("错误 (Step 1): Wan2.7 API 未返回图片")

    # Step 2: image editing, black → white background
    print("Step 2/2: 背景换白 (Wan2.7)...")

    with open(black_path, "rb") as f:
        black_b64 = base64.b64encode(f.read()).decode("utf-8")
    black_data_uri = f"data:image/png;base64,{black_b64}"

    from PIL import Image
    img = Image.open(black_path)
    edit_size = f"{img.width}*{img.height}"

    step2_prompt = "Change the background from black to pure white #FFFFFF. Keep the subject, lighting, details, and position exactly the same. Do not change anything except the background color."

    edit_payload = {
        "model": "wan2.7-image-pro",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": black_data_uri},
                        {"text": step2_prompt}
                    ]
                }
            ]
        },
        "parameters": {
            "size": edit_size,
            "n": 1,
            "watermark": False
        }
    }

    try:
        resp = requests.post(DASHSCOPE_URL, json=edit_payload, headers=headers, timeout=120)
    except requests.RequestException as e:
        raise RuntimeError(f"网络请求失败 - {e}")

    if resp.status_code != 200:
        handle_wan_error(resp, "Step 2")
        raise RuntimeError("Wan2.7 API 调用失败")

    data = resp.json()
    choices = data.get("output", {}).get("choices", [])
    if not choices:
        raise RuntimeError("错误 (Step 2): Wan2.7 API 未返回图片")

    white_path = os.path.join(output_dir, f"{slug}_{ts}_white.png")
    white_saved = False
    for choice in choices:
        for content in choice.get("message", {}).get("content", []):
            if content.get("type") == "image":
                download_wan_image(content["image"], white_path)
                print(f"  -> {white_path}")
                white_saved = True

    if not white_saved:
        raise RuntimeError("错误 (Step 2): Wan2.7 API 未返回图片")

    return black_path, white_path


def generate_black_white(prompt: str, ratio: str = DEFAULT_RATIO, size: str = DEFAULT_SIZE,
                         output_dir: str = "local/output", model: str = "gemini"):
    """Generate black/white background image pair from text description.

    Returns:
        (black_path, white_path) tuple of file paths
    """
    os.makedirs(output_dir, exist_ok=True)

    if model == "wan":
        return bwgen_wan(prompt, ratio, size, output_dir)
    else:
        return bwgen_gemini(prompt, ratio, size, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="使用 Gemini 或 Wan2.7 生成黑白背景双图（bwdiff 前序）")
    parser.add_argument("-p", "--prompt", required=True, help="主体描述")
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
        black_path, white_path = generate_black_white(
            args.prompt, args.ratio, args.size, args.output, args.model
        )
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n完成！黑白双图已保存：")
    print(f"  黑底: {black_path}")
    print(f"  白底: {white_path}")
    print(f"\n继续用 bwdiff 抠图：")
    print(f"  python .claude/skills/bwdiff/scripts/bw_diff.py -b {black_path} -w {white_path}")