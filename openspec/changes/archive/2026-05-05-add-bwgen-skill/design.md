## Context

bwdiff 技能通过黑白像素差分反算 alpha 通道，需要同一主体在纯黑底和纯白底下的两张图。目前用户若没有这种素材，bwdiff 无法使用。bwgen 技能填补这一空缺，通过 Gemini API 从文字描述直接生成所需双图。

现有 gen-image 技能已封装 Gemini 文生图调用，使用 `gemini-3.1-flash-image-preview` 模型。bwgen 在此基础上增加图编辑步骤，形成两步流水线。

## Goals / Non-Goals

**Goals:**
- 从文字描述生成纯黑底（#000000）主体图
- 将黑底图编辑为纯白底（#FFFFFF），保持主体不变
- 输出黑白双图，可直接作为 bwdiff 的 `-b` 和 `-w` 参数
- 复用现有 Gemini API 密钥和 `google-genai` 依赖
- 命令行接口与其他技能脚本风格一致

**Non-Goals:**
- 不支持输入图片（第一步是纯文生图）
- 不调用 bwdiff（职责单一，输出双图即可）
- 不修改现有 gen-image 或 bwdiff 技能
- 不引入新的模型或本地依赖

## Decisions

### 两步串行调用

Step 1 文生图 + Step 2 图编辑。Step 2 以 Step 1 的输出为输入，保证主体位置一致。

Step 1 的 prompt 策略：在用户描述后追加 "pure black background"，不要求用户自己写背景色。

Step 2 的实现：将黑底图作为 `Part.from_bytes` 传入 `contents`，附上 "change background to pure white #FFFFFF, keep subject exactly the same" 类 prompt。

### 复用 Gemini 3.1 Flash Image Preview

与 gen-image 使用相同模型，已验证可用。如后续模型升级，两个技能一起迁移。

### 脚本接口设计

```bash
python bw_gen.py -p "描述" [-r 1:1] [-s 1K] [-o local/output]
```

参数与 gen-image 保持一致（`-p`、`-r`、`-s`、`-o`），降低认知负担。

### 输出文件命名

`<slug>_black.png` 和 `<slug>_white.png`，其中 slug 从用户描述截取。

## Risks / Trade-offs

- **Step 2 编辑可能不够精确**：Gemini 图像编辑可能轻微改变主体细节 → 用明确、约束性强的 prompt；最终质量由 bwdiff 的像素差分来兜底，偏差过大会表现为边缘伪影
- **两步调用增加延迟**：每次运行需两次 API 调用 → 告知用户需等待；后续可考虑是否合并为单次调用
- **API 频率限制**：两次调用可能触发限流 → 脚本添加基础重试机制

## Open Questions

- Gemini 3.1 Flash 对 "change background" 类图像编辑 prompt 的实际响应质量需实测
- 第一步生成的黑底图本身质量（主体与背景的分离度）对第二步编辑影响很大
