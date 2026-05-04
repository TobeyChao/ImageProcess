---
name: game-ui-analyzer
description: Analyzes game screenshots to identify UI components and their visual hierarchy. Use this skill whenever the user asks to analyze, parse, break down, or dissect a game screenshot or image — whether they say "analyze UI", "parse this screenshot", "break down the components", "what's in this game image", or ask to understand the structure of a game's interface. This includes popup marketing images (拍脸图), activity pages, game menus, HUD elements, or any game-related visual composition. Make sure to use this skill for any request involving game UI analysis, interface decomposition, or visual hierarchy analysis of game images.
---


# Game UI Analyzer


Analyzes game screenshots to identify UI components and their visual hierarchy, producing detailed text descriptions suitable for game developers, UI designers, or players documenting game interfaces.


## Input


A game screenshot or image file provided by the user. Read the image file to understand its content before analyzing.


## Output Format


Produce a structured analysis that adapts to the image content. Use this flexible format:


### Opening Statement
Start with a brief (1-2 sentence) overview of what the image represents and its purpose in the game context.


### Layer-Based UI Analysis


Organize the UI using **Layer-based** structure, from back to front:


```
Layer 0 - Background/Environment: [atmosphere, setting, ambient elements]
Layer 1 - Base UI Container: [modal frames, panels, base layouts]
Layer 2 - Secondary Elements: [supporting graphics, decorative elements]
Layer 3 - Primary Content: [main visuals, titles, core information]
Layer 4 - Interactive Elements: [buttons, CTAs, navigation]
Layer 5 - Overlay/Status: [tooltips, notifications, top-bar info]
```


**Adjust the layer count based on the image complexity**:
- Simple HUDs might have 3-4 layers
- Complex popups might have 5-6 layers
- Full-screen maps might need different organization


For each layer, describe:
- **What**: Elements in this layer
- **Where**: Positions and spatial relationships
- **Visual treatment**: Colors, transparency, effects
- **Purpose**: What function this layer serves


### Component Breakdown


Based on the image type, identify relevant component categories (not all may apply):


| Type | Components to Look For |
|------|----------------------|
| **Popup/拍脸图** | Hero image, title, rewards, CTA button, close button, countdown |
| **HUD** | Health/mana bars, minimap, skill icons, quest tracker, chat |
| **Map/关卡** | Nodes, paths, chapter indicators, unlock conditions, rewards preview |
| **Shop/商店** | Currency display, item grid, prices, purchase buttons, tabs |
| **Inventory** | Grid slots, item details, filters, action buttons |


Describe each component with:
- **名称/标签**: What's it called?
- **位置**: Where does it appear?
- **视觉特征**: Colors, icons, animations, glows
- **状态**: Active/inactive, locked/unlocked, completed/pending


### Visual Hierarchy Analysis


Identify **3-5 priority levels** based on the image:


**Priority 1 (Immediate Focus)**: What captures attention first?
**Priority 2 (Secondary Focus)**: What draws the eye next?
**Priority 3 (Supporting Info)**: What do users notice after main elements?
**Priority 4+ (Details)**: Additional context, fine print, decorations


Explain **why** for each: size, contrast, color, animation, position?


### Visual Flow / Eye Path


Describe the natural reading path:
1. Entry point (where eyes land first)
2. Journey (what leads the eye through the screen)
3. Destination (CTA, main action, or exit)


### Design Intent


**Tailor this section to the image type**:


| Image Type | Analyze |
|-----------|---------|
| Promotional popup | Conversion goals, urgency tactics, reward psychology |
| HUD/Gameplay | Information priority, quick-scan usability |
| Map/Progression | Exploration motivation, goal-setting, achievement |
| Shop/Store | Purchase drivers, value perception, scarcity |
| Tutorial/Onboarding | Learning flow, guidance clarity, friction reduction |


Questions to answer:
- What action is this UI designed to drive?
- What emotions or motivations does it tap into?
- How does the design support (or hinder) its purpose?
- What player behavior does it encourage?


## Analysis Principles


1. **Be descriptive, not interpretive** - Describe what you SEE, not what you think the developer intended. Use "appears to be" for speculation.


2. **Spatial reference matters** - Always note positions using consistent spatial terms (center, left, right, top, bottom, corners) and approximate regions.


3. **Color and contrast are key** - Note significant colors, gradients, glows, and high-contrast elements as they determine visual hierarchy.


4. **Recognize common game UI patterns**:
   - 拍脸图 (full-screen popups) - Usually promotional, centered hero content with surrounding rewards
   - HUD elements - Health bars, minimaps, currency displays
   - Activity/event pages - Event titles, reward showcases, countdown timers
   - Menu screens - Navigation options, player status, background environments


5. **Distinguish UI layers** - Separate functional UI (can be closed/minimized) from core game content.


## Example Analysis Structure


```
从所提供的这张游戏截图中，我们可以清晰地分析其UI层次结构和视觉设计。这是[游戏名]的[界面类型：活动弹窗/HUD/地图等]，旨在[核心目的：引导充值/提供信息/驱动探索等]。


## Layer-Based UI Analysis


Layer 0 - Background/Environment:
[描述背景氛围，如深海场景、暗色渐变、粒子特效等]


Layer 1 - Base UI Container:
[描述基础容器，如弹窗边框、面板背景等]


Layer 2 - Secondary Elements:
[描述次要装饰元素，如光效、边框、图标等]


Layer 3 - Primary Content:
[描述主要内容：标题、角色立绘、核心信息等]


Layer 4 - Interactive Elements:
[描述交互元素：按钮、导航、输入框等]


Layer 5 - Overlay/Status (if applicable):
[描述顶层信息：倒计时、状态提示、角标等]


## Component Breakdown


根据图片内容，识别关键组件：


[类型相关组件列表，如：]
- 标题区：[位置、样式、文字内容]
- 核心视觉：[角色/主题图、位置、特征]
- 功能入口：[按钮/节点、位置、状态]
- 信息面板：[数据展示、位置]
- [其他根据实际内容添加...]


## Visual Hierarchy


Priority 1 (Immediate Focus):
[最吸引眼球的元素] - [原因：尺寸/颜色/对比度/位置]


Priority 2 (Secondary Focus):
[次要关注点] - [原因分析]


Priority 3+:
[继续分析...]


## Visual Flow / Eye Path


1. [起点] → 2. [中间点] → 3. [终点/CTA]
[解释为什么视线会这样移动]


## Design Intent


[根据图片类型调整分析重点：]


[拍脸图示例：]
- 核心目标：驱动玩家进行[充值/抽取/参与活动]
- 心理机制：[紧迫感/奖励预期/稀缺性/角色情感连接]
- 设计策略：[进度差距制造焦虑/高价值奖励展示/限时倒计时]


[地图界面示例：]
- 核心目标：引导玩家探索关卡内容
- 心理机制：成就感、探索欲、进度可视化
- 设计策略：中心辐射布局、解锁状态区分、路径引导
```


## Handling Ambiguous Cases


If the image is not a game screenshot or the content is unclear:
- State what you observe clearly
- Note the uncertainty
- Provide the best analysis possible given the available information


If the image contains text that cannot be read (too small, blurry, non-Latin script):
- Describe the text's position and approximate area
- Note that text content could not be fully read
- Estimate character count or text density if possible



