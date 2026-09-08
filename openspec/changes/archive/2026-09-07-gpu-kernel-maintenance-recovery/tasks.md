## 1. API and task contract

- [x] 1.1 Add the default-disabled `allow_kernel_maintenance` field to every GPU driver and managed GPU-suite request, frontend payload, task parameters, and retry path; verify schema/API contract tests preserve `false` when omitted.
- [x] 1.2 Add an explicit operator control and reboot/maintenance warning to the GPU task UI; verify the built request sends the field only for the selected flow.

## 2. Rocky kernel-maintenance recovery

- [x] 2.1 Add a persisted Rocky GPU task phase that detects missing exact current-kernel development packages and, without opt-in, returns an actionable no-mutation failure; verify runner unit tests cover that default.
- [x] 2.2 Implement opt-in same-minor candidate installation with only exact kernel package names and temporary kernel-lock removal; verify generated remote commands never contain a full `yum update`/`dnf update`.
- [x] 2.3 Build and validate the candidate initramfs against detected root-storage modules before changing the default boot entry; verify a missing image or module restores/retains the old default and prevents reboot.
- [x] 2.4 Add reboot recovery that verifies the candidate `uname -r`, reruns the release lock workflow for the running kernel, and resumes the existing Nouveau/driver phases; verify phase transitions and failed-boot behavior with runner tests.

## 3. Documentation and verification

- [x] 3.1 Update architecture and progress documentation with the opt-in boundary, same-minor constraint, initramfs validation, and rollback behavior; verify documentation matches the API default.
- [x] 3.2 Run focused backend tests, frontend type/build checks, OpenSpec strict validation, and the full backend suite; record unrelated pre-existing failures separately.
