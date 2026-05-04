import os, sys, torch, importlib.util, types, argparse
import numpy as np
from PIL import Image, UnidentifiedImageError
from torchvision import transforms

parser = argparse.ArgumentParser(description="使用 BiRefNet 移除图像背景")
parser.add_argument("-i", "--input", required=True, help="输入图像路径")
parser.add_argument("-o", "--output", help="输出图像路径（默认在输入文件名后加 _rmbg）")
parser.add_argument("-m", "--model-dir", required=True, help="模型目录路径，需包含 BiRefNet_config.py、birefnet.py 和 model.safetensors")
parser.add_argument("-t", "--threshold", type=float, default=0.5, help="二值化阈值，范围 0.3-0.7。较低值保留更多半透明细节（发丝），较高值边缘更干净（电商白底图）。默认 0.5")
parser.add_argument("--white-bg", action="store_true", help="输出白底 RGB 图片而非透明 PNG")
parser.add_argument("--no-edge-refine", action="store_true", help="跳过边缘优化（膨胀+高斯模糊），速度更快但边缘可能较粗糙")
args = parser.parse_args()

MODEL_DIR = args.model_dir
IMAGE_PATH = args.input
THRESHOLD = args.threshold

# --- Validate model directory ---
if not os.path.isdir(MODEL_DIR):
    sys.exit(f"模型目录不存在: {MODEL_DIR}")

required_files = ["BiRefNet_config.py", "birefnet.py", "model.safetensors"]
for f in required_files:
    fp = os.path.join(MODEL_DIR, f)
    if not os.path.isfile(fp):
        sys.exit(f"缺少模型文件: {fp}")

# --- Validate input image ---
if not os.path.isfile(IMAGE_PATH):
    sys.exit(f"输入文件不存在: {IMAGE_PATH}")

try:
    img = Image.open(IMAGE_PATH)
    img.verify()
except UnidentifiedImageError:
    sys.exit(f"无法识别的图像格式: {IMAGE_PATH}")
except Exception as e:
    sys.exit(f"无法打开图像: {IMAGE_PATH}\n{e}")

img = Image.open(IMAGE_PATH).convert("RGB")
orig_w, orig_h = img.size

# --- Output path ---
if args.output:
    OUTPUT_PATH = args.output
else:
    suffix = "_whitebg" if args.white_bg else "_rmbg"
    ext = ".jpg" if args.white_bg else ".png"
    base, _ = os.path.splitext(IMAGE_PATH)
    OUTPUT_PATH = base + suffix + ext

# --- Device selection ---
device = "cuda" if torch.cuda.is_available() else "cpu"
if device == "cuda":
    torch.set_float32_matmul_precision('high')
print(f"Using device: {device}")

# --- Load model ---
print("Loading BiRefNet model...")
from transformers import PreTrainedModel

sys.path.insert(0, MODEL_DIR)

# Create a package so relative imports in birefnet.py resolve correctly
PKG = "_rmbg_model"
pkg = types.ModuleType(PKG)
pkg.__path__ = [MODEL_DIR]
sys.modules[PKG] = pkg

# Load BiRefNet_config as a submodule
BiRefNetConfig_path = os.path.join(MODEL_DIR, "BiRefNet_config.py")
spec = importlib.util.spec_from_file_location(f"{PKG}.BiRefNet_config", BiRefNetConfig_path)
config_module = importlib.util.module_from_spec(spec)
sys.modules[f"{PKG}.BiRefNet_config"] = config_module
spec.loader.exec_module(config_module)
BiRefNetConfig = config_module.BiRefNetConfig

# Load birefnet as a submodule — relative imports resolve via the package
birefnet_path = os.path.join(MODEL_DIR, "birefnet.py")
spec = importlib.util.spec_from_file_location(f"{PKG}.birefnet", birefnet_path)
model_module = importlib.util.module_from_spec(spec)
sys.modules[f"{PKG}.birefnet"] = model_module
spec.loader.exec_module(model_module)

model = None
for attr_name in dir(model_module):
    attr = getattr(model_module, attr_name)
    if isinstance(attr, type) and issubclass(attr, PreTrainedModel) and attr != PreTrainedModel:
        model_config = BiRefNetConfig()
        model = attr(model_config)
        break

if model is None:
    sys.exit("Could not find model class in birefnet.py")

weights_path = os.path.join(MODEL_DIR, "model.safetensors")
import safetensors.torch
model.load_state_dict(safetensors.torch.load_file(weights_path))
model.eval()

try:
    model.to(device)
except RuntimeError as e:
    if "CUDA" in str(e) or "out of memory" in str(e).lower():
        print(f"GPU 不可用，回退到 CPU: {e}")
        device = "cpu"
        model.to(device)
    else:
        raise

print("Model loaded OK")
print(f"Image size: {orig_w}x{orig_h}")

# --- Process image ---
transform = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

inp = transform(img).unsqueeze(0).to(device)

with torch.no_grad():
    try:
        out = model(inp)
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            print("CUDA OOM, 回退到 CPU...")
            model.to("cpu")
            inp = inp.to("cpu")
            device = "cpu"
            out = model(inp)
        else:
            raise

    if isinstance(out, (list, tuple)):
        mask_tensor = out[-1]
        if isinstance(mask_tensor, (list, tuple)):
            mask_tensor = mask_tensor[0]
    else:
        mask_tensor = out

    if mask_tensor.dim() == 4:
        mask_tensor = mask_tensor.squeeze(1)
    mask_tensor = mask_tensor[0]

mask = mask_tensor.sigmoid().cpu().numpy()

# 边缘优化：膨胀连接断点 + 高斯模糊平滑
if not args.no_edge_refine:
    try:
        from scipy import ndimage
        mask_dilated = ndimage.binary_dilation(mask > 0.5, iterations=2)
        mask_smooth = ndimage.gaussian_filter(mask_dilated.astype(np.float32), sigma=1.5)
        mask = mask * 0.5 + mask_smooth * 0.5
    except ImportError:
        pass  # scipy 未安装时静默跳过，用原始 mask

mask = (mask >= THRESHOLD).astype(np.float32)
mask = (mask * 255).clip(0, 255).astype(np.uint8)
mask_img = Image.fromarray(mask).resize((orig_w, orig_h), Image.LANCZOS)

if args.white_bg:
    result = Image.new("RGB", (orig_w, orig_h), (255, 255, 255))
    result.paste(img, (0, 0), mask_img)
else:
    result = img.convert("RGBA")
    r, g, b, _ = result.split()
    result = Image.merge("RGBA", (r, g, b, mask_img))

result.save(OUTPUT_PATH)
print(f"Saved: {OUTPUT_PATH}")
