# HypoPG selected Intel Mac retry

Created 18 October 2026 to retry the selected HypoPG 1.4.3 publication target on an Intel Mac runner after correcting the verification profile's source list. The workflow exists on `spike` but cannot be dispatched by filename until it reaches the default branch, so a change to `target.json` starts this bounded push-triggered attempt.

`target.json` supplies the exact PostgreSQL release and a positive attempt number. The workflow validates that request, resolves the selected HypoPG release from the support declaration, and builds and verifies the publication archives. Increment `attempt` to request another run of the same target. The retry succeeds when archive construction and both fresh-runner verification cases pass and the workflow retains the resulting publication evidence. Retire this experiment after the selected workflow can be dispatched directly from `spike`.
