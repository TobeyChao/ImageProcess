## ADDED Requirements

### Requirement: rmbg core logic as reusable functions
The system SHALL provide `load_model(model_dir, device=None)` and `process_image(input_path, model, device, threshold, edge_refine, white_bg)` as importable functions from `rmbg_process.py`, with the CLI block guarded by `if __name__ == "__main__"`.

#### Scenario: Import from external module
- **WHEN** another Python module executes `from skills.rmbg.scripts.rmbg_process import load_model, process_image`
- **THEN** the functions are available without side effects (no argparse, no sys.exit)
- **AND** the CLI behavior remains unchanged when the script is executed directly

#### Scenario: process_image returns PIL Image
- **WHEN** `process_image()` completes successfully
- **THEN** it returns a `PIL.Image.Image` object in RGBA or RGB mode
- **AND** the caller is responsible for saving to disk

### Requirement: bwdiff core logic as reusable functions
The system SHALL provide `bw_diff(black_path, white_path)` as an importable function from `bw_diff.py`, returning a PIL Image.

#### Scenario: Import from external module
- **WHEN** another Python module executes `from skills.bwdiff.scripts.bw_diff import bw_diff`
- **THEN** the function is available without side effects
- **AND** the CLI behavior remains unchanged when the script is executed directly

#### Scenario: bw_diff returns RGBA Image
- **WHEN** `bw_diff()` completes successfully
- **THEN** it returns a `PIL.Image.Image` object in RGBA mode with computed alpha channel

### Requirement: bwgen core logic as reusable functions
The system SHALL provide `generate_black_white(prompt, ratio, size, output_dir, model)` as an importable function from `bw_gen.py`, returning `(black_path, white_path)`.

#### Scenario: Import from external module
- **WHEN** another Python module executes `from skills.bwgen.scripts.bw_gen import generate_black_white`
- **THEN** the function is available without side effects
- **AND** the CLI behavior remains unchanged when the script is executed directly

### Requirement: gen-image core logic as reusable functions
The system SHALL provide `generate_image(prompt, ratio, size, output_dir, model)` as an importable function from `gen_image.py`, returning the output file path.

#### Scenario: Import from external module
- **WHEN** another Python module executes `from skills.gen_image.scripts.gen_image import generate_image`
- **THEN** the function is available without side effects
- **AND** the CLI behavior remains unchanged when the script is executed directly
