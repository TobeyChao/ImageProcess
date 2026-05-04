# 黑白差分去背景 — 设计说明

日期: 2026-05-03
实际实现: 2026-05-04 — bwdiff 最终作为独立技能（`.claude/skills/bwdiff/`）实现，拥有独立的 SKILL.md 和脚本。

## 概述

新增 `bw_diff.py` 脚本（独立技能 `.claude/skills/bwdiff/`），通过黑底图和白底图的像素差值反算 alpha 通道，实现传统算法去背景，作为 BiRefNet 模型方案的轻量补充。

## 文件

- 新增: `.claude/skills/bwdiff/scripts/bw_diff.py`
- 新增: `.claude/skills/bwdiff/SKILL.md`

## 命令行接口

```
python bw_diff.py -b <黑底图> -w <白底图> [-o <输出路径>]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `-b` / `--black` | 是 | 黑底图路径 |
| `-w` / `--white` | 是 | 白底图路径 |
| `-o` / `--output` | 否 | 输出路径，默认：黑底图文件名 + `_bwdiff.png` |

## 算法

逐像素、三通道平均：

```
diff = mean(Cw - Cb)
a = 1 - diff / 255          // alpha，钳位 [0, 1]
Cf = Cb / a                 // a > 0 时
Cf = 0                      // a = 0 时（全透明）
```

输出：原分辨率 RGBA PNG。

## 处理流程

1. 读取黑底图和白底图（RGB）
2. 校验尺寸一致，不一致则报错退出
3. 逐像素计算 alpha 和前景色（numpy 向量化）
4. 合成 RGBA，保存 PNG

## 依赖

- pillow
- numpy

不需要 torch/transformers。

## 边界与异常

| 情况 | 处理 |
|------|------|
| 尺寸不一致 | 报错退出，提示两张图分辨率 |
| alpha 计算溢出 | 钳位至 [0, 255] |
| a = 0 的像素 | 前景色设为 (0, 0, 0)，alpha 为 0 |
| 文件不存在 | argparse 自动报错 |

## SKILL.md

bwdiff 拥有独立的 SKILL.md（`.claude/skills/bwdiff/SKILL.md`），定义独立的触发规则和调用接口，不再作为 rmbg 的子模式。