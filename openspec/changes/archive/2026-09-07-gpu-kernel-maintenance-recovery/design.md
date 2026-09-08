## Context

See [proposal.md](proposal.md). The current GPU runner has a reboot-aware
driver phase and task-resume machinery, while Rocky release locking is a
separate script. The incident showed that a pinned 9.4 kernel can lack matching
development packages and that a newly installed kernel can be unbootable if its
initramfs was not generated.

## Goals / Non-Goals

**Goals:**

- Provide one explicit operator opt-in for controlled Rocky kernel maintenance
  across single, batch, and managed GPU entry points.
- Make the maintenance sequence resumable and auditable as part of the existing
  GPU task, including boot artifact validation before reboot.
- Preserve the currently fixed Rocky minor version and avoid implicit full
  package updates.

**Non-Goals:**

- Supporting cross-minor Rocky upgrades, arbitrary RPM repositories, or
  automatic kernel maintenance on Ubuntu.
- Deleting the previous kernel or changing the default behavior of existing API
  callers that omit the new option.
- Retrying a failed CUDA task independently of its GPU-driver prerequisite.

## Decisions

### Additive opt-in request field

Add `allow_kernel_maintenance` as an optional boolean, defaulting to `false`,
to all GPU-driver and managed GPU-suite request contracts. Persist it in task
parameters so retries and startup recovery preserve the operator's decision.
This is safer and backward compatible than overloading the existing
force-driver-reinstall flag.

### A dedicated GPU maintenance phase

Use a persisted GPU task phase before the existing driver preparation phase.
It will: inspect exact running-kernel packages; when absent and opted in,
temporarily remove only kernel version locks; install exact candidate kernel,
kernel-devel and headers from the already-fixed repositories; build an
initramfs; validate root-storage modules; set the candidate as default only
after validation; then reboot. After reconnect, verify `uname -r`, rerun the
release lock script to lock the new running kernel, and proceed through the
existing Nouveau/driver state machine.

Keeping this inside the existing task permits existing recovery code, task logs,
and managed-suite ordering to remain authoritative. A separate hidden task
would complicate dependency ordering and leave CUDA able to start without a
verified driver.

### Root-storage-aware initramfs validation

Discover the current root backing stack and require only its corresponding
drivers in the candidate initramfs. NVMe, device-mapper/LVM, and XFS are
required for the observed incident path. Validation failure restores the prior
default boot entry and prevents reboot. This is safer than assuming package
post-install hooks produced a usable image.

### No full system update

GPU dependency preparation installs only named build dependencies and exact
current-kernel development packages. It never calls `yum update`/`dnf update`.
The kernel-maintenance path names its candidate packages explicitly, so release
and non-kernel packages cannot drift as a side effect.

## Risks / Trade-offs

- [Candidate kernel still fails after initramfs validation] → retain the
  previous BLS entry, require reboot recovery to detect failed boot, and keep a
  console-visible old-kernel fallback.
- [Older locked repositories do not contain a usable candidate] → fail before
  altering boot settings with the exact missing package/version evidence.
- [Restart during maintenance] → persist a phase and backup metadata before
  reboot; startup recovery resumes or reports the known phase.
- [Operator unintentionally authorizes a reboot] → default false, clear UI
  warning and API field, audit the selected option.

## Migration Plan

1. Deploy the additive backend/frontend contract with the option disabled by
   default; existing task payloads remain unchanged.
2. Validate the maintenance phase with unit tests covering unavailable exact
   packages, initramfs validation failure, successful reboot resume, and lock
   restoration.
3. Roll back by disabling use of the option; already-created tasks retain their
   phase data and do not require a schema migration.
