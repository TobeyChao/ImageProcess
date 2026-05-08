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

## 一键安装

```bash
# 使用项目提供的 requirements.txt 一次性安装所有依赖
pip install -r requirements.txt
```

**手动安装各项依赖**：
```bash
pip install torch torchvision transformers safetensors pillow numpy timm kornia scipy gradio modelscope
```

**可选依赖**（边缘优化，推荐安装）：
```bash
pip install scipy
```

如需 GPU 加速（推荐），替换 CUDA 版 PyTorch：

```bash
# CUDA 12.x
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## 模型下载

RMBG-2.0 模型可从 ModelScope 获取：

```bash
pip install modelscope
modelscope download --model AI-ModelScope/RMBG-2.0 --local_dir "<你的模型目录路径>"
```

## 常见问题

| 问题 | 解决方法 |
|------|----------|
| `ModuleNotFoundError: No module named 'safetensors'` | `pip install safetensors` |
| `Could not find model class in birefnet.py` | 确认 `birefnet.py` 存在且完整 |
| 推理速度慢 | 安装 CUDA 版 PyTorch，或将 MODEL_DIR 内模型迁移至 SSD |
| 输出图像边缘粗糙 | 安装 `scipy` 启用边缘优化（膨胀+高斯模糊），或调整 `-t` 阈值 |



