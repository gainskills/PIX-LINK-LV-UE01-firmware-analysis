# Project handoff / 项目记忆

Updated 2026-10-27. This is the project context to read when continuing work in this repository. Device-specific records are in the ignored `.private/PROJECT-MEMORY.md` if present. Native project membership and a resumable continuation were created through Codex APIs; no databases were edited manually.

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

## Native conversation history (2026-10-27)

The native project is now named `repeater` and rooted at this repository. Both the original conversation and `Repeater firmware — complete history continuation` are assigned to it. Twelve related records (original sessions plus continuation) were assigned through native APIs; unrelated sessions were excluded. The continuation was reopened in a separate native process with this working directory and AGENTS.md; all171 source turn IDs were present in its paginated history. No model turn or AP action was started by verification.

Run `./resume-history.sh` from this repository to resume the continuation. It reads the private saved thread ID and passes an explicit `--cd` to Codex. The original thread remains open elsewhere, so it was not forcibly opened by a second writer. Raw session snapshots, prompt/index history, native project/resume verification and memory snapshots are in ignored `.private/session-history/`; latest.json identifies the latest export. An export is a dated snapshot; this original conversation may continue appending afterward. This procedure changes native project association, not merely file placement.

## Pending source change (2026-11-01)

Upstream manual SSID/security entry no longer requires a scan result; English/Chinese guidance covers hidden networks. Credential validation remains, and scanned selections still supply channel hints. Offline regression `node logic/web-update/test_manual_upstream.cjs` passes. The minified controller was regenerated and `.work/` assembled with private inputs. No firmware image was rebuilt or flashed; hidden-network association/channel discovery is not hardware-verified. The tested release hash above is unchanged.

At the user’s request, a separate UI-refresh image was then built: `firmware/releases/lv-ue01-hidden-ssid-760196ce.uimage.bin`, SHA256 `760196cec03633113aacb618d7c33ec6cb464b714dbcbd71212b21336e54037a`. Only the controller allocation and its response-length stub differ in the decoded main; driver/auth/PHY diagnostics preserved. Image 718108 bytes, compressed655978, headroom52786. CRCs, decompression, byte scope, embedded resources, manual-entry controller regressions and eight EN/ZH browser scan checks passed offline. Builder: `logic/web-update/build_ui_refresh.py` after minification. Original release retained. New image not flashed or boot/hidden-association tested.

## Mode-switch review (2026-11-01)

See `analysis/reviews/MODE-SWITCH-REVIEW.md`. Both repeater save paths now set native WLN_APCLI_CONFIGED=1 (vendor wizard/monitor disassembly supports its role). Mode changes default to hidden local SSID and WPS off; user can change visibility. Existing management address/LAN_IP_MODE=1 preserved. Four mocked EN/ZH browser save/readback/reboot cases pass, alongside manual-upstream tests. New separate candidate `firmware/releases/lv-ue01-hidden-ssid-9875ca7c.uimage.bin` was built offline, not flashed. This is not a confirmed explanation/fix for the user’s current client-IP failure. Preserve previous releases.

Pending UI source refinement: when selected mode differs from saved mode, Connect & restart is disabled (handler also rejects it) and EN/ZH guidance directs users to Save & restart. Mode transitions now have one full-configuration save path; upstream-only connection remains available for an already saved repeater. No release image rebuilt for this refinement; 9875ca7c does not include it.

## Latest user-requested test image (2026-11-01)

User reports wired DHCP failure with 9875ca7c and no AP lease visible on upstream router; user then physically reset the device before further capture. This reset is a user action, not a successful factory-reset verification. No live fault capture was possible; known management endpoints timed out. Generated `firmware/releases/lv-ue01-hidden-ssid-7d30631a.uimage.bin`, SHA256 `7d30631ab80fdcd78c678da1f20866457e13521e8b2604ca0b9561d27ce5d69a`, with the single-save mode-transition UI. 718108 bytes, compressed656094, headroom52670. Container/byte-scope checks, manual-upstream regressions, 2 EN/ZH mode-save cases, 4 factory-default UI checks and 8 scan browser checks passed offline. Not flashed, boot-tested or a verified DHCP fix. Original 81db3776 remains unchanged. Earlier 760196ce and 9875ca7c artifacts/sidecars were already absent at final verification; removed their dangling checksum entries, did not delete those artifacts. Full hashes remain in this memory/history.

## Current management-page follow-up (2026-11-01)

Live status evidence showed that repeater association was absent despite valid repeater/DHCP-off configuration. The reported upstream network is 5 GHz/channel 36, while the board's management UI exposes only 2.4 GHz channels 1--14; use a compatible 2.4 GHz upstream network or dual-band repeater hardware. This is not an Ethernet DHCP-server setting defect.

The current source work adds an Overview upstream state, maps a valid empty association response to disconnected, removes the WPS default-state note, and improves System-form spacing. The focused EN/ZH browser regression plus existing manual-upstream, mode-switch and factory-default regressions passed. `analysis/reviews/MODE-SWITCH-REVIEW.md` contains requirements and test evidence. No AP action, flash, reboot, upload, commit or candidate release occurred.

Packaging is blocked: the legacy full-resource builder reports that the changed static `lan.htm` exceeds the canonical dashboard allocation, while the specialized current release builder only replaces controller JavaScript. A usable candidate requires an explicit follow-up to extend that specialized builder to update the canonical HTML resource and callbacks, with resource bounds, byte-scope, decompression and CRC checks. Do not use a runtime-DOM workaround unless the user chooses that less-clean alternative.

## Management-page checklist completed

The packaging limitation described above is resolved. Candidate `firmware/releases/lv-ue01-hidden-ssid-08323845.uimage.bin`, SHA256 `08323845b16a147354cbba3230a370288b0be27381cea0cac0bf869ad1a5c599`, includes the Overview upstream status, disconnected/unavailable distinction, removed WPS note and System spacing. HTML10503/10552 bytes after merging duplicate CSS. Builder supports bounded canonical HTML plus controller and response lengths; independent `logic/web-update/verify_ui_refresh.py` validates resource/byte scope and full container integrity. Image718108, compressed656220, headroom52544. Six status/layout, two mode-save, eight scan and four factory-render checks plus manual controller tests passed offline; Chrome closed. Details in MODE-SWITCH-REVIEW.md and 08323845-test-readiness.json. Not flashed or a DHCP/Ethernet fix; original tested hash/reset limitations preserved.

## False Disconnected status correction

User reports Disconnected despite connected upstream. Empty legacy `ApCliConnStatus` also appears in a historically known-working capture; 08323845’s empty-to-disconnected mapping was wrong. Latest offline candidate: `firmware/releases/lv-ue01-repeater-69ce20ae.uimage.bin`, SHA256 `69ce20ae08603c7c2debd02ed6e3f468153f29f2afff8d3724d38feb11c6cedc`. Adds a 24-byte read-only native status-export helper and one status-renderer call redirection; reads the numeric state used by original index (2 connected/1 connecting/0 disconnected). Empty/unknown legacy results now Unavailable. No driver/PHY/config/auth changes in this correction. Independent integrity, resource/byte-scope checks,14 EN/ZH browser scenarios, controller tests and isolated Unicorn ABI/read-only tests passed. Image718108, compressed656325, headroom52439. Not flashed/hardware-tested; management URL requested, no new live capture obtained. See MODE-SWITCH-REVIEW.md. Preserve81db3776 and experimental/PHY/reset limitations.

## Release naming and baseline archive

At the user's request, removed the old81db3776 path from releases by archiving its identical bytes at `firmware/intermediates/phy-diagnostic/startup-trace/startup-trace.uimage.NOT-FOR-FLASHING.bin`. Current release renamed to `lv-ue01-repeater-69ce20ae.uimage.bin`; hash unchanged. Builder/verifier and workspace map now use the archived baseline; release.json and SHA256SUMS identify only the current candidate. No new firmware bytes, flash or device changes. Candidate remains hardware-unverified; historical tested baseline remains available for reproducibility.

## User deployment report — 2026-11-01

User reports flashing `lv-ue01-repeater-69ce20ae.uimage.bin` to a device and beginning testing; they will report problems. This is user-reported deployment, not independent image readback, status validation, or proof of a DHCP/Ethernet fix. Do not assume every device or older installation record now identifies this build. Leave the device undisturbed; no polling, scan, reboot, reset, configuration change or additional flash is requested. Wait for user findings while allowing useful offline work.

## Management port save correction — 2026-11-01

User reports Upstream management port does not save via Save & restart. Offline reproduction confirms `guard()` rejected an active upstream-port change before POST. Fixed guard to allow port changes while upstream management stays enabled; normalize old default HTTP port80 for redirection. Verified save/readback/reboot ordering retained. Source and packaged controller pass12 EN/ZH port-save/redirect/static-access/validation/rejected-import scenarios, plus manual-entry, mode-switch and upstream-status regressions. Candidate `firmware/releases/lv-ue01-repeater-0eda26d6.uimage.bin`, SHA256 `0eda26d6c2efe11018a8d611427d67553fe5bfd155e08b3efbeab53eaa436a8b`:718108 bytes, compressed656243, container headroom52521; independent integrity/resource checks passed. Only controller allocation/response length differ from69ce20ae. Not flashed or hardware-verified; user-tested69ce20ae remains unchanged. No device action taken. Details in MODE-SWITCH-REVIEW.md; new regression `test_management_port_browser.cjs`.

## Latest deployment and release retention — 2026-11-01

User reports flashing0eda26d6 and confirms the management-port change works. No independent device readback or long-term stability validation. At the user's request, releases now retain only `lv-ue01-repeater-0eda26d6.uimage.bin` and its metadata/checksum; superseded69ce20ae image and sidecar removed. Historical hashes and investigation records remain, as does required81db3776 build baseline under intermediates. Latest image bytes/hash unchanged; no build, upload, live access or restart performed. Keep only the latest release image going forward unless an older artifact is required as a reproducible build input. Continue undisturbed user testing.
