## Requirements

### Requirement: Generate black background image from text
The system SHALL accept a text description and generate an image of the described subject on a pure black (#000000) background via Gemini API.

#### Scenario: Successful black background generation
- **WHEN** user provides a text prompt "一只橘猫"
- **THEN** the system calls Gemini to generate an image of an orange cat on a pure black background
- **AND** saves the result as `<slug>_black.png`

### Requirement: Edit black background to white background
The system SHALL take the generated black-background image and edit it to replace the black background with pure white (#FFFFFF), preserving the subject.

#### Scenario: Successful background swap
- **WHEN** a black-background image is available from step 1
- **THEN** the system calls Gemini with the image and a prompt to change background to white
- **AND** saves the result as `<slug>_white.png`

### Requirement: Output images compatible with bwdiff
The system SHALL output two images of identical dimensions with the same subject, one on black background and one on white background, suitable for use as bwdiff inputs.

#### Scenario: Output files for bwdiff
- **WHEN** both generation steps complete
- **THEN** two PNG files exist in the output directory
- **AND** both files have identical pixel dimensions
- **AND** the files are named `<slug>_black.png` and `<slug>_white.png`

### Requirement: Configurable aspect ratio and resolution
The system SHALL support configurable aspect ratio and resolution, with defaults of 1:1 and 1K respectively.

#### Scenario: Default parameters
- **WHEN** user does not specify aspect ratio or resolution
- **THEN** the system uses 1:1 aspect ratio and 1K resolution

#### Scenario: Custom parameters
- **WHEN** user specifies `-r 16:9 -s 2K`
- **THEN** both generation steps use 16:9 aspect ratio and 2K resolution

### Requirement: Reuse existing Gemini API key
The system SHALL read the Gemini API key with priority order: value from `local/config.json` > `GEMINI_API_KEY` environment variable.

#### Scenario: Config file takes priority
- **WHEN** both `local/config.json` contains `gemini_api_key` and `GEMINI_API_KEY` environment variable is set
- **THEN** the system uses the value from `local/config.json`

#### Scenario: Environment variable fallback
- **WHEN** `local/config.json` does not exist or has no `gemini_api_key`, but `GEMINI_API_KEY` is set
- **THEN** the system uses the environment variable value

#### Scenario: Missing API key
- **WHEN** neither `local/config.json` gemini_api_key nor `GEMINI_API_KEY` environment variable is set
- **THEN** the system outputs an error message and exits with non-zero code
