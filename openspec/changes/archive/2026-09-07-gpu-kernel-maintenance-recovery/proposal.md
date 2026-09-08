## Why

Rocky 9.4 servers pinned to an older kernel can lack matching `kernel-devel` and
`kernel-headers` in their fixed-version repositories. NVIDIA installation then
fails before CUDA starts. Operators currently have to perform a risky, manual
kernel-maintenance sequence; a new kernel also must not become the default until
its initramfs has been validated for the server's NVMe/LVM/XFS root path.

## What Changes

- Add an explicit, default-disabled GPU installation option that authorizes
  same-minor-release kernel maintenance and one recovery reboot when the running
  kernel lacks matching development packages.
- On Rocky 9, select an available kernel only from the already locked release
  repositories; preserve the Rocky minor version and never use a full-system
  `yum update` as a substitute.
- Generate and validate the candidate kernel's initramfs before changing the
  default boot entry, including NVMe, LVM/device-mapper, and XFS requirements
  when those back the current root filesystem.
- Resume the original GPU-driver task after a verified reboot, relock the newly
  running kernel, then let the existing suite proceed to CUDA.
- Keep the existing safe default: when the option is absent or false, report the
  missing exact development package without changing kernels or rebooting.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `gpu-compute-provisioning`: GPU provisioning gains an opt-in, same-minor
  Rocky kernel-maintenance recovery path with boot-artifact validation and
  task-resume guarantees.

## Impact

- Backend task request schemas, managed-suite creation, GPU driver runner and
  task recovery state handling.
- GPU installation UI/API contract gains an additive optional boolean.
- Remote Rocky hosts may install exact kernel packages and reboot only after an
  operator enables the option; no new third-party dependency is required.
