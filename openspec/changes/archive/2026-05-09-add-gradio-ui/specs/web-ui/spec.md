## ADDED Requirements

### Requirement: Zero-dependency bootstrap script
The system SHALL provide a `main.py` script that uses only Python standard library modules and can be executed immediately after `git clone` without any `pip install`.

#### Scenario: First launch
- **WHEN** user runs `python main.py` in a freshly cloned repository
- **THEN** the script starts a local HTTP server on port 7860
- **AND** serves a setup page that detects and displays the current environment status

#### Scenario: Environment already ready
- **WHEN** user runs `python main.py` and all dependencies, models, and configurations are already in place
- **THEN** the script launches the Gradio application directly without showing the setup wizard

### Requirement: Environment detection
The system SHALL detect and report the status of: virtual environment existence, Python dependencies, model files, and API key configuration.

#### Scenario: Missing dependencies detected
- **WHEN** the bootstrap script runs and `gradio` cannot be imported
- **THEN** the setup page shows "Dependencies: Missing" with a list of required packages
- **AND** displays a "One-Click Install" button

#### Scenario: Missing model detected
- **WHEN** the bootstrap script runs and `local/models/RMBG-2.0/model.safetensors` does not exist
- **THEN** the setup page shows "Model: Missing (1.7 GB)"

### Requirement: Real-time setup progress via SSE
The system SHALL stream setup progress to the browser using Server-Sent Events, including pip install output and model download progress.

#### Scenario: pip install progress
- **WHEN** user clicks "One-Click Install" and `pip install` is running
- **THEN** each line of pip output is pushed to the browser in real time via SSE

#### Scenario: Model download progress
- **WHEN** model download is in progress
- **THEN** the browser displays a progress bar with percentage and downloaded/total size

#### Scenario: Setup completion
- **WHEN** all setup tasks complete successfully
- **THEN** the page shows "Setup Complete" and an "Launch App" button

### Requirement: Gradio Web UI with tabbed layout
The system SHALL provide a Gradio Web UI accessible at `localhost:7860` with tabs for Settings, Background Removal, Black-White Diff, Black-White Generate, Image Generate, and Pipeline.

#### Scenario: Tab navigation
- **WHEN** user opens the UI
- **THEN** they see six tabs: 设置, 去背景, 黑白差分, 生黑白底图, 生图, 一键管线
- **AND** clicking each tab reveals its form controls

### Requirement: Settings Tab with persistent configuration
The system SHALL provide a Settings tab with fields for model directory, Gemini API Key, and DashScope API Key, persisted to `local/config.json`.

#### Scenario: First-time configuration
- **WHEN** user fills in the API Key fields and clicks save
- **THEN** the values are saved to `local/config.json`
- **AND** all other tabs can read these values for their operations

#### Scenario: Settings persistence across restarts
- **WHEN** user restarts the application
- **THEN** previously saved model directory and API Keys are loaded and pre-filled in the Settings tab

#### Scenario: API Key field privacy
- **WHEN** user views the Settings tab
- **THEN** API Key fields are rendered as password type (obscured by default)

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
