# Human review queue

No pending decision blocks the current local builds.

## Proposed local Lume iteration overview

Proposed design text: Create a clean Lume macOS VM with a working compiler, then clone it while stopped into a build VM and a clean verification VM. Start each VM headlessly in the background, wait for SSH readiness, run build commands over SSH, and transfer source and final archives with `scp`. Keep iterative build files under the guest user's home directory. Verify final archive bytes in the clean clone. Gracefully stop or delete only project-specific VMs. Linux uses Docker or Lume with the same separation between building and clean verification. GitHub builds follow passing local checks for both ARM64 targets.

This sequence has been checked on Lume 0.6.1 with a macOS 26.6.2 ARM64 guest: C compilation, detached boot and log path, SSH, key-based `scp`, cloning, clean-VM isolation, home-directory persistence after shutdown, and deletion of a throwaway VM. This Lume version has no `lume cp` command.

This is a documentation proposal for human review and does not block local builds.
