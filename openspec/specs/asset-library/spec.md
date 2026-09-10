## Purpose

Define the controlled operational asset library so Linux scripts, Windows stress materials, and related metadata can be cataloged, validated, previewed, downloaded, and constrained to their intended use instead of becoming arbitrary remote execution input.

## Requirements

### Requirement: Script assets are validated and categorized before use

The system SHALL maintain script metadata and files with category, version, enabled state, risk metadata, and parameter schema. Upload and execution eligibility SHALL enforce the relevant allowlist, extension, and parameter-validation rules.

#### Scenario: An administrator uploads an allowed Linux script
- **WHEN** a file matches an allowed library category and validation succeeds
- **THEN** it becomes a cataloged asset with metadata available for approved task selection

#### Scenario: A disabled or invalid asset is selected for execution
- **WHEN** task creation references a disabled asset or invalid parameters
- **THEN** the request is rejected before remote execution begins

### Requirement: Windows stress materials are local operator aids

The system SHALL allow supported Windows script materials to be previewed, downloaded, and used to generate copyable PowerShell commands. It SHALL not dispatch or execute those Windows materials through the Linux remote-task runner.

#### Scenario: An operator generates a Windows stress command
- **WHEN** the operator chooses a supported module and duration in the Windows stress interface
- **THEN** the system renders a copyable command using the selected values without creating a remote task
