## ADDED Requirements

### Requirement: Zero-dependency bootstrap script
The system SHALL provide a `main.py` script that uses only Python standard library modules and can be executed immediately after `git clone` without any `pip install`.

#### Scenario: First launch
- **WHEN** user runs `python main.py` in a freshly cloned repository
- **THEN** the script prints environment status to the terminal
- **AND** prompts the user for each required setup step (venv, deps, model) with `[Y/n]` confirmation
- **AND** offers optional GPU support installation with `[y/N]` confirmation

#### Scenario: Environment already ready
- **WHEN** user runs `python main.py` and all dependencies, models, and configurations are already in place
- **THEN** the script launches the Gradio application directly without any prompts

### Requirement: Environment detection
The system SHALL detect and report the status of: virtual environment existence, Python dependencies, model files, and API key configuration.

#### Scenario: Missing dependencies detected
- **WHEN** the bootstrap script runs and `gradio` cannot be imported
- **THEN** the terminal prints "📚 依赖包... ❌ 缺少 13 个: gradio, torch, ..."
- **AND** lists dependency installation as a required step

#### Scenario: Missing model detected
- **WHEN** the bootstrap script runs and `local/models/RMBG-2.0/model.safetensors` does not exist
- **THEN** the terminal prints "🧠 模型... ❌ 需要下载 (~840 MB)"

### Requirement: Background Removal Tab (rmbg)
The system SHALL provide a tab for removing image backgrounds using BiRefNet, with configurable threshold, edge refinement toggle, and white background output option.

#### Scenario: Remove background with default settings
- **WHEN** user uploads an image, selects a model directory, and clicks "Process"
- **THEN** the result is displayed alongside the original image
- **AND** the result is an RGBA PNG with transparent background

#### Scenario: Adjust threshold via slider
- **WHEN** user adjusts the threshold slider (0.3-0.7)
- **THEN** the threshold value is displayed next to the slider with semantic labels ("发丝保留" at low end, "边缘干净" at high end)

### Requirement: Black-White Diff Tab (bwdiff)
The system SHALL provide a tab for removing backgrounds using the black-white difference algorithm, accepting a black-background image and a white-background image.

#### Scenario: Successful diff
- **WHEN** user uploads a black-background image and a white-background image, then clicks "Process"
- **THEN** the result is displayed as an RGBA PNG with transparent background

#### Scenario: Size mismatch error
- **WHEN** the two uploaded images have different dimensions
- **THEN** an error message is displayed: "两张图片尺寸不一致"

### Requirement: Black-White Generate Tab (bwgen)
The system SHALL provide a tab for generating black and white background image pairs from a text description, with configurable aspect ratio, resolution, and model backend.

#### Scenario: Generate with Gemini
- **WHEN** user enters a prompt, selects Gemini as backend, and clicks "Generate"
- **THEN** both the black-background and white-background images are generated and displayed

### Requirement: Image Generate Tab (gen-image)
The system SHALL provide a tab for generating images from a text description, with configurable aspect ratio, resolution, and model backend.

#### Scenario: Generate image
- **WHEN** user enters a prompt and clicks "Generate"
- **THEN** the generated image is displayed with a download button

### Requirement: Pipeline Tab (bwgen → bwdiff)
The system SHALL provide a Pipeline tab that chains bwgen and bwdiff operations, accepting a text description and producing a background-removed image in one action.

#### Scenario: One-click pipeline
- **WHEN** user enters a prompt, selects parameters, and clicks "One-Click Execute"
- **THEN** bwgen generates black/white background images
- **AND** bwdiff processes them into a transparent PNG
- **AND** all three images (black, white, result) are displayed
