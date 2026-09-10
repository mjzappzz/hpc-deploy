## Purpose

Define administrative authorization, auditability, settings control, and reusable command records so high-impact operations are explicitly confirmed, scoped to the browser context, and reviewable after the fact.

## Requirements

### Requirement: High-risk operations require scoped administrator authorization

The system SHALL verify the administrator password before granting administrative authority and SHALL require a valid, tab-bound administrator token for protected settings, asset, cleanup, archive, and audit operations. Password values SHALL not be returned through settings interfaces.

#### Scenario: A protected request has no valid administrator authority
- **WHEN** a caller invokes a protected endpoint without a valid scoped token
- **THEN** the endpoint rejects the request and no protected mutation occurs

#### Scenario: An administrator changes the password
- **WHEN** the current password is verified and the new value satisfies policy
- **THEN** the system updates the credential without exposing its plaintext in any settings response

### Requirement: Governance actions are auditable and command records are non-executing

The system SHALL retain structured audit records for governed operations while filtering sensitive input fields. The common-operations command catalog SHALL support administrator-confirmed edits and browser-local pinning but SHALL not execute catalog content.

#### Scenario: A cleanup operation is performed
- **WHEN** an authorized cleanup request succeeds or fails
- **THEN** an audit record captures its outcome and safe contextual detail without passwords, tokens, raw commands, or secrets

#### Scenario: An operator copies a saved operations command
- **WHEN** an operator selects a catalog entry
- **THEN** the system provides its visible formatted content for copying and does not send it to a managed server for execution
