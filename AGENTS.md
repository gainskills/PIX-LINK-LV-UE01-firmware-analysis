# Repository instructions

Read `MEMORY.md` and the root README before continuing this firmware project. When present, read the local ignored `.private/PROJECT-MEMORY.md` for device/evidence locations. Keep private details out of public documents and commit messages.

The working repository is this `repeater` folder. The former ESP32 project is unrelated and contains no current AP work. Do not recreate a compatibility directory or symlink there.

Edit source in `logic/`, then assemble `.work/` using `tools/prepare_workspace.py`. For local private evidence use `--include-private`; this rebases runtime record paths without modifying archived originals. Do not edit `.private/workbench/` as if it were the public source tree or delete it as generated output.

Preserve the known tested firmware artifact hash. File reorganization does not authorize rebuilding/reflashing the running AP. The user is conducting long-term testing; do not disturb the stable connection or repeatedly request playback/standby comparisons. Progress with offline work, and capture faults when the user reports them. No UART, multimeter or spare switch is available.

Keep the limits of the initialization/reset review and unresolved PHY models explicit. Experimental diagnostic results are not a confirmed Ethernet fix. Never publish or stage ignored private/runtime/dependency directories. Stop temporary background processes once their bounded task completes.
