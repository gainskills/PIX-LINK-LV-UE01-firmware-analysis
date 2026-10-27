# Project handoff / 项目记忆

Updated 2026-10-24. This is the project context to read when continuing work in this repository. Device-specific records are in the ignored `.private/PROJECT-MEMORY.md` if present. No global/session memory store has been modified.

## Scope and current build

PIX-LINK LV-UE01-V1.0 board, MediaTek MT7628KN; vendor eCos firmware v28K.RPT.20220716. This project patches an existing binary; it does not rebuild or upgrade the vendor OS, Wi-Fi/Ethernet drivers or network stack.

Installed experimental diagnostic build: **81db3776**, full uImage SHA256 `81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377`. It includes the bilingual image-free management UI, HTTP authentication patch, WPS default off, and startup PHY diagnostics. Vendor version text is unchanged. The release bytes have not changed during file migration.

On 2026-10-23 the user reported almost two days without the previous interruption and will continue long-term testing. Treat this as a user report, not a verified fix. No hardware reset/flash was performed during migration or memory relocation.

## Investigation findings

The X99 uses a manually fixed IP, so DHCP alone cannot explain the historical failure. LV-UE01 has independent power. Failures were intermittent and also occurred outside playback/standby transitions; a reference wireless-to-Ethernet adapter was stable. An iPad also had an affected wired connection and recovered after repeated cable reconnects.

Observed faulty state: port0 link down, BMSR7849/7849, AP management still reachable. Port0 POA link is bit25; bit0 is reference speed. `81818301` is DOWN, `83818301` is UP/100M. BMSR must be read twice because of latch behavior.

Actual startup trace records: first PHY call is interface enable (caller80003960, parent8000479c), entering with link down. Second is the monitor direct request (caller8014e338), entering with POA83818301: an already established link is then reset by the original function. That function writes BMCR3900 to PHY0–4, delays with argument300, then writes3300; it does not verify negotiation success before returning. Delay wall units are not calibrated.

This is a real observed link-disrupting path, not a proven cause of prolonged failures. This boot later recovered. A different proposed same-iteration interface-restart+direct-request double call is supported by static/component analysis but has not been proved on hardware; its full continuous Unicorn model raises an unresolved exception. Do not count it as a successful reproduction. Raw CP0 Count is not wall time and decreased between startup records.

## Initialization limits

Only the WPS byte in the embedded factory-default table differs from stock. Defaults: AP, DHCP server on, LAN192.168.10.1, upstream management off with stored port8080, visible/open local Wi-Fi, vendor admin defaults retained. Switching/saving repeater settings in the new UI disables local DHCP and enables upstream management. Loading a page does not apply these changes. These UI rules are not a proven global backend constraint.

Normal upgrade/reboot/config preservation are hardware-verified. Factory-default UI rendering passed offline in English/Chinese. Physical Reset, blank/corrupt configuration boot and reset-to-repeater provisioning have not been hardware-verified. Do not reset the stable device to fill this gap without a separate user decision.

## Working layout and checks

- `logic/`: editable code. `analysis/`: sanitized reports. `firmware/`: unchanged binary inputs/releases.
- `.private/workbench/`: preserved original evidence; do not silently rewrite archived bytes or expose them publicly.
- `tools/prepare_workspace.py`: assemble public inputs in ignored `.work/`. Use `--include-private` for local backup/fault work; private JSON paths are rebased in `.work/`, not in archived originals. A workspace already containing private evidence requires that flag to avoid mislabeling it public-only.
- `.venv/` and `node_modules/`: pinned, Git-ignored local tools. Do not rely on old temporary dependency directories.
- Published copies are sanitized; the untouched originals and their hash index remain private.
- Offline validation: 31 diagnostic regressions, 9 capture-parser tests, 20 native-auth cases, 20 pre-upload cases, 8 scan-browser checks, 4 factory-default browser checks. Workspace relocation has focused tests under `tools/test_prepare_workspace.py`.
- Current overview: README; reset evidence: analysis/reviews/INITIALIZATION-RESET-REVIEW.md; live-deployment evidence: local private workbench deployment; original UI restoration plan: analysis/plans/2026-10-18-ap-management-restoration.md (historical, not the current release size/status).

## User preferences and next work

Continue useful offline firmware analysis/preparation without repeatedly asking to proceed. Long-term fault reproduction belongs to the user; when a fault is reported, capture the existing state before changing it. Do not repeatedly rerun normal-state/playback comparisons or block all work waiting for the next failure. Explain uncertainty precisely and retain dated evidence.

The user has no USB serial adapter, multimeter or spare switch; do not make those prerequisites. New firmware flashes, physical resets and disruptive live changes require a concrete candidate and explicit authorization. Prior flash authorization is not blanket permission for a different build. Do not leave background monitors/terminals running; close temporary sessions and report actual state.

The Git repository is local only: no commit/push/GitHub release has been performed by this migration. Do not stage `.private/`, `.work/`, `.venv/` or node_modules, and do not publish credentials, raw full-Flash images, configuration exports or raw packet captures.
