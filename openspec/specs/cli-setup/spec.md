## ADDED Requirements

### Requirement: Console-based environment status display
The system SHALL detect and display environment status in the terminal with clear pass/fail/warning indicators for: Python version, virtual environment, dependencies, GPU support, and model availability.

#### Scenario: All checks pass
- **WHEN** all environment checks pass
- **THEN** each check displays a ✅ indicator with version/path details
- **AND** the script proceeds directly to launching Gradio without prompting

#### Scenario: Some checks fail
- **WHEN** virtual environment is missing and dependencies are not installed
- **THEN** those checks display a ❌ indicator
- **AND** the script shows a summary of required vs optional setup steps before prompting

#### Scenario: GPU detected but not enabled
- **WHEN** an NVIDIA GPU is detected but torch is CPU-only
- **THEN** the GPU check shows ⚠️ with GPU name and "CUDA 未启用"
- **AND** GPU installation is listed as an optional step

### Requirement: Interactive step-by-step confirmation
The system SHALL prompt the user for confirmation before each setup step, distinguishing between required steps (default Y) and optional steps (default N).

#### Scenario: Required step confirmation
- **WHEN** virtual environment needs to be created
- **THEN** the system prompts "是否创建虚拟环境？[Y/n]"
- **AND** pressing Enter (default Y) starts the creation
- **AND** typing "n" skips and exits with a message

#### Scenario: Optional step confirmation
- **WHEN** GPU support installation is available but not required
- **THEN** the system prompts "是否安装 CUDA 版 PyTorch 启用 GPU 加速？[y/N]"
- **AND** pressing Enter (default N) skips the step
- **AND** typing "y" starts the installation

#### Scenario: Required step skipped
- **WHEN** user declines a required step
- **THEN** the system prints "已取消" and exits with code 0

### Requirement: Real-time terminal progress output
The system SHALL stream pip install and model download output directly to the terminal.

#### Scenario: pip install output
- **WHEN** `pip install -r requirements.txt` is running
- **THEN** each line of pip output is printed to stdout immediately

#### Scenario: Model download output
- **WHEN** modelscope model download is in progress
- **THEN** progress lines are printed to stdout as they arrive

### Requirement: Direct Gradio launch after setup
The system SHALL launch the Gradio app as a subprocess on the default port after setup completes, without a reverse proxy.

#### Scenario: Successful launch
- **WHEN** all required setup steps complete
- **THEN** the system prints the app URL and opens the browser
- **AND** the Gradio process runs on its default port (7860)

#### Scenario: Graceful shutdown
- **WHEN** user presses Ctrl+C
- **THEN** the Gradio subprocess is terminated
- **AND** the script exits cleanly
