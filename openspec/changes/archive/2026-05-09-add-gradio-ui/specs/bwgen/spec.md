## MODIFIED Requirements

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
