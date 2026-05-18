import os, sys, torch
import numpy as np
from PIL import Image
from torchvision import transforms


def load_model(model_dir, device=None):
    """Load BiRefNet model from model_dir. Returns (model, device)."""
    if not os.path.isdir(model_dir):
        raise FileNotFoundError(f"模型目录不存在: {model_dir}")

    required_files = ["BiRefNet_config.py", "birefnet.py", "model.safetensors"]
    for f in required_files:
        if not os.path.isfile(os.path.join(model_dir, f)):
            raise FileNotFoundError(f"缺少模型文件: {os.path.join(model_dir, f)}")

    if device is None:
        if torch.cuda.is_available():
            device = "cuda"
        elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    if device == "cuda":
        torch.set_float32_matmul_precision('high')

    print(f"Using device: {device}")

    from transformers import AutoModelForImageSegmentation

    model = AutoModelForImageSegmentation.from_pretrained(
        model_dir, trust_remote_code=True, local_files_only=True
    )

    try:
        model.to(device)
    except RuntimeError as e:
        msg = str(e).lower()
        if "cuda" in msg or "mps" in msg or "out of memory" in msg:
            print(f"GPU 不可用，回退到 CPU: {e}")
            device = "cpu"
            model.to(device)
        else:
            raise

    model.eval()
    print("Model loaded OK")
    return model, device


def process_image(image, model, device, threshold=0.5, edge_refine=False, white_bg=False):
    """Remove background from PIL RGB Image. Returns PIL Image (RGBA or RGB if white_bg)."""
    orig_w, orig_h = image.size

    transform = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    inp = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        try:
            out = model(inp)
        except RuntimeError as e:
            msg = str(e).lower()
            if "out of memory" in msg or "mps" in msg:
                print(f"{device.upper()} 推理失败，回退到 CPU: {e}")
                model.to("cpu")
                inp = inp.to("cpu")
                device = "cpu"
                out = model(inp)
            else:
                raise

    # Aligned with official BRIA RMBG-2.0 demo: preds[-1].sigmoid().cpu()
    if isinstance(out, (list, tuple)):
        mask_tensor = out[-1]
    else:
        mask_tensor = out

    mask_tensor = mask_tensor[0]  # first batch item
    if mask_tensor.dim() == 3:
        mask_tensor = mask_tensor.squeeze(0)

    mask_tensor = mask_tensor.sigmoid().cpu()

    if device == "mps":
        try:
            torch.mps.empty_cache()
        except (AttributeError, RuntimeError):
            pass

    # Convert to PIL mask and resize to original dimensions (official demo pattern)
    pred_pil = transforms.ToPILImage()(mask_tensor)
    mask = pred_pil.resize((orig_w, orig_h), Image.LANCZOS)

    # --- Commented out: edge_refine ---
    # if edge_refine:
    #     try:
    #         from scipy import ndimage
    #         mask_arr = np.array(mask).astype(np.float32) / 255.0
    #         mask_dilated = ndimage.binary_dilation(mask_arr > 0.5, iterations=2)
    #         mask_smooth = ndimage.gaussian_filter(mask_dilated.astype(np.float32), sigma=1.5)
    #         mask_arr = mask_arr * 0.5 + mask_smooth * 0.5
    #         mask = Image.fromarray((mask_arr * 255).astype(np.uint8))
    #     except ImportError:
    #         pass

    # --- Commented out: threshold binarization ---
    # mask_arr = (np.array(mask).astype(np.float32) / 255.0 >= threshold).astype(np.float32)
    # mask = Image.fromarray((mask_arr * 255).astype(np.uint8))

    # --- Commented out: white_bg output ---
    # if white_bg:
    #     result = Image.new("RGB", (orig_w, orig_h), (255, 255, 255))
    #     result.paste(image, (0, 0), mask)
    #     return result

    result = image.convert("RGBA")
    r, g, b, _ = result.split()
    result = Image.merge("RGBA", (r, g, b, mask))

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="使用 BiRefNet 移除图像背景")
    parser.add_argument("-i", "--input", required=True, help="输入图像路径")
    parser.add_argument("-o", "--output", help="输出图像路径（默认在输入文件名后加 _rmbg）")
    parser.add_argument("-m", "--model-dir", required=True, help="模型目录路径")
    # parser.add_argument("-t", "--threshold", type=float, default=0.5, help="二值化阈值 (0.3-0.7)")
    # parser.add_argument("--white-bg", action="store_true", help="输出白底 RGB 图片而非透明 PNG")
    # parser.add_argument("--no-edge-refine", action="store_true", help="跳过边缘优化")
    args = parser.parse_args()

    try:
        img = Image.open(args.input)
        img.verify()
    except Exception:
        sys.exit(f"无法识别的图像格式: {args.input}")

    img = Image.open(args.input).convert("RGB")

    model, device = load_model(args.model_dir)
    result = process_image(img, model, device)
    # result = process_image(img, model, device, threshold=args.threshold,
    #                        edge_refine=not args.no_edge_refine, white_bg=args.white_bg)

    if args.output:
        output_path = args.output
    else:
        # suffix = "_whitebg" if args.white_bg else "_rmbg"
        # ext = ".jpg" if args.white_bg else ".png"
        base, _ = os.path.splitext(args.input)
        output_path = base + "_rmbg.png"

    result.save(output_path)
    print(f"Saved: {output_path}")
