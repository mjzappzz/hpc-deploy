## Purpose

Define the managed-server inventory and connectivity capability so operators can safely register Linux/HPC hosts, establish their access posture, and maintain trustworthy hardware and availability information.

## Requirements

### Requirement: Server records preserve a unique management target

The system SHALL create, read, update, archive, restore, and delete server records containing the SSH endpoint, authentication mode, and operator-facing inventory metadata. A live server host SHALL not be registered twice, and archive state SHALL be changed only through the dedicated archive operations.

#### Scenario: An operator attempts to add a duplicate host
- **WHEN** a create request uses a host already present in the active inventory
- **THEN** the request is rejected with the existing server identity and no duplicate record is written

#### Scenario: An operator archives a server
- **WHEN** an administrator archives a managed server
- **THEN** the server is frozen for operational use and its displayed connectivity state becomes unknown until it is restored

### Requirement: Connectivity and hardware state are evidence-based

The system SHALL test SSH connectivity, probe hardware, expose tag summaries, and support public-key inspection and deployment using each server's configured authentication method. A failed or partial probe SHALL not replace the last complete hardware inventory.

#### Scenario: GPU probing is incomplete after a server reconnects
- **WHEN** OS, CPU, memory, or disk probing cannot complete together with the GPU portion
- **THEN** the system records the current connectivity outcome but preserves the last complete hardware inventory

#### Scenario: Public key deployment targets multiple servers
- **WHEN** an operator deploys the managed public key to eligible servers
- **THEN** each target is authenticated independently, already-present keys are not duplicated, and one failure does not prevent other targets from being processed
