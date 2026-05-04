# 模型安装与环境配置

## 模型信息

- **模型**：BiRefNet（RMBG-2.0）
- **运行时通过 `-m` 参数指定模型目录**

该目录下需包含以下文件：

```
<model-dir>/
├── BiRefNet_config.py
├── birefnet.py
└── model.safetensors
```

## Python 依赖安装

```bash
pip install torch torchvision transformers safetensors pillow numpy timm kornia
```

**可选依赖**（边缘优化，推荐安装）：
```bash
pip install scipy
```

如需 GPU 加速（推荐），安装支持 CUDA 的 PyTorch：

```bash
# CUDA 12.x
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## 模型下载

RMBG-2.0 模型可从 Hugging Face 获取：

```bash
huggingface-cli download briaai/RMBG-2.0 --local-dir "<你的模型目录路径>"
```

或通过 ComfyUI 的模型管理器安装。

## 常见问题

| 问题 | 解决方法 |
|------|----------|
| `ModuleNotFoundError: No module named 'safetensors'` | `pip install safetensors` |
| `Could not find model class in birefnet.py` | 确认 `birefnet.py` 存在且完整 |
| 推理速度慢 | 安装 CUDA 版 PyTorch，或将 MODEL_DIR 内模型迁移至 SSD |
| 输出图像边缘粗糙 | 安装 `scipy` 启用边缘优化（膨胀+高斯模糊），或调整 `-t` 阈值 |



