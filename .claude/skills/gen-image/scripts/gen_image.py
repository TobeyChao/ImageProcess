from google import genai
from google.genai import types
import os
import re
import argparse
from datetime import datetime

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("请设置环境变量 GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

DEFAULT_RATIO = "1:1"   # "1:1","1:4","1:8","2:3","3:2","3:4","4:1","4:3","4:5","5:4","8:1","9:16","16:9","21:9"
DEFAULT_SIZE  = "1K"    # "512", "1K", "2K", "4K"

parser = argparse.ArgumentParser(description="使用 Gemini 生成图像")
parser.add_argument("-p", "--prompt", required=True, help="图像生成提示词")
parser.add_argument("-r", "--ratio", default=DEFAULT_RATIO, help="宽高比，如 1:1, 16:9, 9:16 等")
parser.add_argument("-s", "--size", default=DEFAULT_SIZE, help="分辨率：512, 1K, 2K, 4K")
parser.add_argument("-o", "--output", default="local/output", help="输出目录（相对于工作目录）")
args = parser.parse_args()

output_dir = args.output
os.makedirs(output_dir, exist_ok=True)

config = types.GenerateContentConfig(
    response_modalities=['TEXT', 'IMAGE'],
    image_config=types.ImageConfig(
        aspect_ratio=args.ratio,
        image_size=args.size
    ),
)

## gemini-2.5-flash-image
## gemini-3.1-flash-image-preview
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=[args.prompt],
    config=config
)

caption = ""
for part in response.parts:
    if part.text is not None:
        caption = part.text.strip()
        print(caption)
    elif part.inline_data is not None:
        image = part.as_image()
        if caption:
            slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", caption)[:40].strip("_")
        else:
            slug = "generated"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_{timestamp}.png"
        image.save(os.path.join(output_dir, filename))
        print(f"图片已保存: {filename}")

