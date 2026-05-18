## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Real-time setup progress via SSE
**Reason**: Browser-based setup replaced by terminal console interaction. Terminal output is inherently real-time via stdout, no SSE needed.
**Migration**: None — this functionality is replaced by `cli-setup` spec's "Real-time terminal progress output" requirement.

### Requirement: Gradio Web UI with tabbed layout
**Reason**: The Gradio Web UI itself is unchanged. Only the bootstrap path (how main.py reaches app.py) changes. This requirement is removed from web-ui because the reverse-proxy port coordination aspect is gone.
**Migration**: Gradio app runs on its default port (7860) instead of 7861 behind a proxy. The app itself is identical.

### Requirement: Settings Tab with persistent configuration
**Reason**: The Settings Tab in the Gradio UI itself is unchanged. Removed from web-ui spec scope because the bootstrap no longer involves browser-based config.
**Migration**: Settings continue to work identically in the Gradio UI.
