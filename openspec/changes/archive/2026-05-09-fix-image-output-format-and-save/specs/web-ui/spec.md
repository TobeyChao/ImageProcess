## ADDED Requirements

### Requirement: Image components use correct PNG format
The system SHALL set `format="png"` on all `gr.Image` output components, and `image_mode="RGBA"` on components that display transparency (rmbg output, bwdiff result, pipeline result).

#### Scenario: Transparent image preserves alpha
- **WHEN** user processes an image through rmbg or bwdiff
- **THEN** the displayed result image uses PNG format with RGBA color mode
- **AND** transparent areas remain transparent, not filled with white

#### Scenario: Opaque image uses PNG format
- **WHEN** user generates an image through gen-image or bwgen
- **THEN** the displayed result image uses PNG format with default (RGB) color mode

### Requirement: Download via dedicated DownloadButton
The system SHALL provide `gr.DownloadButton` components for result images instead of relying on Gradio's built-in download button, which SHALL be disabled by setting `buttons=["fullscreen"]` on all `gr.Image` output components.

#### Scenario: Download triggers file save, not navigation
- **WHEN** user clicks the "下载结果 PNG" button
- **THEN** the browser triggers a file download dialog
- **AND** does NOT navigate away from the current page
- **AND** the downloaded file is in PNG format

#### Scenario: Fullscreen button still available
- **WHEN** user views a result image
- **THEN** the fullscreen button is visible and functional
- **AND** only the fullscreen button appears (no download or share button)

### Requirement: Rmbg result auto-save
The system SHALL save rmbg processing results to `local/output/rmbg/` with filename `<original_name>_rmbg.png` and provide the file path for download.

#### Scenario: Successful rmbg processing with auto-save
- **WHEN** user processes an image `cat.jpg` through rmbg
- **THEN** the result is saved as `local/output/rmbg/cat_rmbg.png`
- **AND** the download button points to this file

### Requirement: Bwdiff result auto-save
The system SHALL save bwdiff processing results to `local/output/bwdiff/` with a timestamp-based filename and provide the file path for download.

#### Scenario: Successful bwdiff processing with auto-save
- **WHEN** user processes black/white images through bwdiff
- **THEN** the result is saved as `local/output/bwdiff/<timestamp>_bwdiff.png`
- **AND** the download button points to this file

### Requirement: Pipeline bwdiff result auto-save
The system SHALL save the bwdiff result from the pipeline to `local/output/bwdiff/` with a timestamp-based filename.

#### Scenario: Successful pipeline with auto-save
- **WHEN** user runs the pipeline (bwgen → bwdiff)
- **THEN** the bwgen black and white images are saved (existing behavior)
- **AND** the bwdiff result is saved as `local/output/bwdiff/<timestamp>_pipeline.png`
- **AND** download buttons point to all three files
