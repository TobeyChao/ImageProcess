from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError, APIError
import os
import re
import sys
import argparse
from datetime import datetime

VALID_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9"}
VALID_SIZES = {"512", "1K", "2K", "4K"}
DEFAULT_RATIO = "1:1"
DEFAULT_SIZE = "1K"

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("错误: 未设置环境变量 GEMINI_API_KEY", file=sys.stderr)
    print("请在 .claude/settings.local.json 中配置，或 export GEMINI_API_KEY=...", file=sys.stderr)
    sys.exit(1)

parser = argparse.ArgumentParser(description="使用 Gemini 生成黑白背景双图（bwdiff 前序）")
parser.add_argument("-p", "--prompt", required=True, help="主体描述")
parser.add_argument("-r", "--ratio", default=DEFAULT_RATIO, help=f"宽高比（默认 {DEFAULT_RATIO}）")
parser.add_argument("-s", "--size", default=DEFAULT_SIZE, help=f"分辨率：512, 1K, 2K, 4K（默认 {DEFAULT_SIZE}）")
parser.add_argument("-o", "--output", default="local/output", help="输出目录（默认 local/output）")
args = parser.parse_args()

if args.ratio not in VALID_RATIOS:
    print(f"错误: 不支持的宽高比 '{args.ratio}'，可选: {', '.join(sorted(VALID_RATIOS))}", file=sys.stderr)
    sys.exit(1)
if args.size not in VALID_SIZES:
    print(f"错误: 不支持的分辨率 '{args.size}'，可选: {', '.join(sorted(VALID_SIZES))}", file=sys.stderr)
    sys.exit(1)

output_dir = args.output
try:
    os.makedirs(output_dir, exist_ok=True)
except OSError as e:
    print(f"错误: 无法创建输出目录 {output_dir}: {e}", file=sys.stderr)
    sys.exit(1)

client = genai.Client(api_key=api_key)

def handle_api_error(e: APIError, step: str) -> None:
    """Print a user-friendly error message based on API error type."""
    code = getattr(e, "code", None)
    if code == 401 or code == 403:
        print(f"错误 ({step}): API 密钥无效或无权访问", file=sys.stderr)
        print("请检查 GEMINI_API_KEY 是否正确且未过期", file=sys.stderr)
    elif code == 429:
        print(f"错误 ({step}): API 配额用尽或请求过于频繁", file=sys.stderr)
        print("请稍后重试或切换 API 密钥", file=sys.stderr)
    elif code == 400:
        msg = str(e).lower()
        if "location" in msg or "region" in msg:
            print(f"错误 ({step}): 当前地区不支持 Gemini 图片生成", file=sys.stderr)
            print("请使用代理或等待服务在更多地区开放", file=sys.stderr)
        elif "safety" in msg:
            print(f"错误 ({step}): 内容被安全过滤器拦截，请修改提示词后重试", file=sys.stderr)
        else:
            print(f"错误 ({step}): 请求参数无效 - {e}", file=sys.stderr)
    elif code and 500 <= code < 600:
        print(f"错误 ({step}): Gemini 服务器错误 (HTTP {code})，请稍后重试", file=sys.stderr)
    else:
        print(f"错误 ({step}): API 调用失败 - {e}", file=sys.stderr)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
slug = re.sub(r"[^\w一-鿿]+", "_", args.prompt)[:40].strip("_")

try:
    chat = client.chats.create(
        model="gemini-2.5-flash-image",
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=args.ratio,
                image_size=args.size,
            ),
        )
    )
except ClientError as e:
    handle_api_error(e, "初始化会话")
    sys.exit(1)
except ServerError as e:
    handle_api_error(e, "初始化会话")
    sys.exit(1)
except Exception as e:
    print(f"错误: 创建 Gemini 会话失败 - {e}", file=sys.stderr)
    sys.exit(1)

# ── Step 1: generate image with black background ──
print("Step 1/2: 生成黑底图...")
step1_prompt = f"{args.prompt}, pure black background #000000 solid background, do not add any elements beyond the described subject, no shadows, no reflections, no ground plane, no environment"

try:
    step1_response = chat.send_message(step1_prompt)
except ClientError as e:
    handle_api_error(e, "Step 1")
    sys.exit(1)
except ServerError as e:
    handle_api_error(e, "Step 1")
    sys.exit(1)
except Exception as e:
    print(f"错误 (Step 1): 网络请求失败 - {e}", file=sys.stderr)
    print("请检查网络连接后重试", file=sys.stderr)
    sys.exit(1)

if step1_response.parts is None:
    print("错误 (Step 1): API 返回空响应，可能被安全过滤器拦截，请修改提示词后重试", file=sys.stderr)
    sys.exit(1)

black_path = os.path.join(output_dir, f"{slug}_{timestamp}_black.png")
black_saved = False
for part in step1_response.parts:
    if part.text is not None:
        print(part.text.strip())
    elif part.inline_data is not None:
        try:
            image = part.as_image()
            image.save(black_path)
            print(f"  -> {black_path}")
            black_saved = True
        except Exception as e:
            print(f"错误 (Step 1): 保存图片失败 - {e}", file=sys.stderr)
            sys.exit(1)

if not black_saved:
    print("错误 (Step 1): API 未返回图片，可能被安全过滤器拦截，请修改提示词后重试", file=sys.stderr)
    sys.exit(1)

# ── Step 2: edit image, black → white background ──
print("Step 2/2: 背景换白...")
step2_prompt = "Change the background from black to pure white #FFFFFF. Keep the subject, lighting, details, and position exactly the same. Do not change anything except the background color."

try:
    step2_response = chat.send_message(step2_prompt)
except ClientError as e:
    handle_api_error(e, "Step 2")
    sys.exit(1)
except ServerError as e:
    handle_api_error(e, "Step 2")
    sys.exit(1)
except Exception as e:
    print(f"错误 (Step 2): 网络请求失败 - {e}", file=sys.stderr)
    print("请检查网络连接后重试", file=sys.stderr)
    sys.exit(1)

if step2_response.parts is None:
    print("错误 (Step 2): API 返回空响应，可能被安全过滤器拦截，请重试", file=sys.stderr)
    sys.exit(1)

white_path = os.path.join(output_dir, f"{slug}_{timestamp}_white.png")
white_saved = False
for part in step2_response.parts:
    if part.text is not None:
        print(part.text.strip())
    elif part.inline_data is not None:
        try:
            image = part.as_image()
            image.save(white_path)
            print(f"  -> {white_path}")
            white_saved = True
        except Exception as e:
            print(f"错误 (Step 2): 保存图片失败 - {e}", file=sys.stderr)
            sys.exit(1)

if not white_saved:
    print("错误 (Step 2): API 未返回图片，请重试", file=sys.stderr)
    sys.exit(1)

print(f"\n完成！黑白双图已保存：")
print(f"  黑底: {black_path}")
print(f"  白底: {white_path}")
print(f"\n继续用 bwdiff 抠图：")
print(f"  python .claude/skills/bwdiff/scripts/bw_diff.py -b {black_path} -w {white_path}")
