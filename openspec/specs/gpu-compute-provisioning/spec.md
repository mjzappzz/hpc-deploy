## Purpose

Define controlled NVIDIA driver and CUDA Toolkit provisioning so operators can select supported runtime assets, apply them according to detected operating-system policy, and receive post-install verification without conflating driver and toolkit state.

## Requirements

### Requirement: NVIDIA driver assets have controlled lifecycle and use

The system SHALL manage long-lived NVIDIA driver library assets separately from temporary task uploads, restrict accepted driver package forms and classifications, and associate selected assets with their installation tasks.

#### Scenario: An operator uploads a temporary driver for a task
- **WHEN** a valid NVIDIA `.run` package is uploaded for one installation task
- **THEN** it is stored as a temporary task asset, can be used by that task, and is not presented as a permanent library asset

#### Scenario: An incompatible driver asset is uploaded
- **WHEN** the submitted filename or classification does not meet the driver-library policy
- **THEN** the upload is rejected before it becomes available for deployment

### Requirement: Provisioning selects supported execution and verification paths

The system SHALL choose the supported driver installation workflow from the target's detected operating system and SHALL install requested CUDA Toolkit versions without silently replacing an existing driver. It SHALL verify the resulting runtime using the relevant observable command. For Rocky 9, a GPU installation request MAY explicitly authorize same-minor-release kernel maintenance when the currently running kernel lacks matching development packages; without that authorization, the system SHALL leave the running kernel unchanged and return an actionable failure. The system SHALL NOT use a full system update as a substitute for matching kernel development packages.

#### Scenario: Driver replacement requires a reboot
- **WHEN** a supported forced driver installation completes with a reboot-required state
- **THEN** the task enters reboot recovery, reconnects when available, and verifies the observed driver state before terminal completion

#### Scenario: CUDA Toolkit installation is requested
- **WHEN** an operator selects a supported CUDA version for an eligible server
- **THEN** the system validates existing driver availability, installs only the toolkit path, and verifies the result with `nvcc --version`

#### Scenario: Matching Rocky development packages are unavailable without authorization
- **WHEN** a Rocky 9 GPU installation finds that the running kernel lacks matching `kernel-devel` or `kernel-headers` and kernel maintenance is not authorized
- **THEN** the system SHALL not alter kernel packages or boot settings and SHALL report that maintenance-window kernel recovery is required

#### Scenario: Authorized Rocky kernel maintenance has a boot-safe candidate
- **WHEN** a Rocky 9 GPU installation finds missing matching development packages and the operator authorizes kernel maintenance
- **THEN** the system SHALL select packages only from the target's fixed minor-version repositories, generate and validate the candidate initramfs before changing the default boot entry, reboot, relock the verified running kernel, and resume the GPU installation

#### Scenario: Candidate Rocky initramfs is not boot-safe
- **WHEN** authorized kernel maintenance cannot generate an initramfs containing the modules required for the target's root storage path
- **THEN** the system SHALL retain or restore the prior default boot entry, SHALL not reboot into the candidate kernel, and SHALL fail with the validation reason
