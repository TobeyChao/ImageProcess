## ADDED Requirements

### Requirement: Model loading via HuggingFace AutoModelForImageSegmentation

The system SHALL load the BiRefNet model using `AutoModelForImageSegmentation.from_pretrained(model_dir, trust_remote_code=True, local_files_only=True)` instead of manual `importlib` loading.

#### Scenario: Load model from local directory

- **WHEN** `load_model(model_dir)` is called with a valid model directory containing `BiRefNet_config.py`, `birefnet.py`, `model.safetensors`, and `config.json`
- **THEN** the model is loaded successfully and returned as `(model, device)` tuple

#### Scenario: Missing model directory

- **WHEN** `load_model(model_dir)` is called with a path that does not exist
- **THEN** an error is raised indicating the model directory is not found

#### Scenario: GPU device auto-detection

- **WHEN** `load_model(model_dir)` is called without an explicit device
- **THEN** the system SHALL auto-detect and use CUDA if available, MPS if available, otherwise CPU

#### Scenario: Output format compatible with existing registry

- **WHEN** `load_model(model_dir)` completes
- **THEN** the returned tuple `(model, device)` SHALL be compatible with `ModelRegistry.get_or_load()` callers in `app.py`

### Requirement: Image processing aligned with official demo

The system SHALL process images using the same inference pipeline as the official BRIA RMBG-2.0 demo: resize to 1024×1024, normalize with ImageNet stats, forward pass, extract `preds[-1].sigmoid().cpu()`, and resize the mask back to original dimensions.

#### Scenario: Process a valid RGB image

- **WHEN** `process_image(pil_image, model, device)` is called with a valid PIL RGB image
- **THEN** the function SHALL return a PIL RGBA image with transparency channel derived from the model's mask output

#### Scenario: GPU fallback on OOM

- **WHEN** the GPU runs out of memory during inference
- **THEN** the system SHALL catch the error and retry inference on CPU automatically

#### Scenario: Output mask dimensions

- **WHEN** `process_image` completes
- **THEN** the output image SHALL have the same width and height as the input image

### Requirement: Sigmoid output as continuous alpha channel

The system SHALL use the raw sigmoid output as the alpha channel without binarization threshold, matching the official BRIA RMBG-2.0 demo behavior.

#### Scenario: Alpha channel is continuous

- **WHEN** `process_image()` processes an image
- **THEN** the alpha channel SHALL be derived directly from the sigmoid output without any threshold binarization

### Requirement: Advanced options reserved but not exposed

The advanced processing options (edge_refine, white_bg) SHALL remain in the `process_image()` function signature with default False but SHALL NOT be exposed in the Web UI.

#### Scenario: Process image with defaults

- **WHEN** `process_image()` is called without optional parameters
- **THEN** it SHALL process with edge_refine=False, white_bg=False

#### Scenario: UI does not expose advanced options

- **WHEN** the rmbg Tab is rendered
- **THEN** the edge_refine checkbox and white_bg checkbox SHALL be hidden (visible=False)
