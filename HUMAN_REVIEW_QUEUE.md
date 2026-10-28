# Human review queue

No pending decision blocks the current local builds.

## Proposed local Lume iteration overview

Proposed design text: A retained, stopped Lume base VM contains macOS, Xcode Command Line Tools and `pkg-config`. It contains no PostgreSQL or extension build outputs. Local macOS iteration uses a build clone for compilation and a separate clean clone to verify the final archive bytes. The clones start without a viewer; SSH runs build and verification commands, and `scp` transfers source and archives. Build files live under the guest user's home directory so they survive a graceful shutdown. Project clones can be stopped or deleted after use. Linux uses local Docker containers or Lume VMs with separate build and clean verification environments. GitHub builds begin after both ARM64 targets pass locally.

This sequence has been checked on Lume 0.6.1 with a macOS 26.6.2 ARM64 guest: C compilation, detached boot and log path, SSH, key-based `scp`, cloning, clean-VM isolation, home-directory persistence after shutdown, and deletion of a throwaway VM. This Lume version has no `lume cp` command.

This is a documentation proposal for human review and does not block local builds.
