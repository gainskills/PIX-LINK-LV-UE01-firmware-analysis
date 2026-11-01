# AP to repeater configuration review — 2026-11-01

## Upstream management port save — candidate 0eda26d6

User reports that changing the upstream management port and using Save & restart does not save it. Reproduced offline through the active upstream URL: `guard()` throws `currentUpstream` before configuration submission whenever the port changes. This unnecessarily requires an alternate fixed address, even when no fixed address is enabled. The save flow already supports verified import, reboot through the old origin, and delayed navigation to the new port.

The guard now permits a port change while upstream management stays enabled. Disabling the active access path remains guarded. The redirect comparison also normalizes the browser's empty default-HTTP port to 80. Port range and fixed-address port-80 collision validation remain. Connect & restart continues to preserve management settings; use full Save & restart for a port edit.

The regression first failed on the original guard with no submitted configuration. Twelve EN/ZH scenarios now pass against source and minified controller: active upstream access, old port 80, fixed-address access, invalid input, port collision, and rejected configuration readback. Requests are mocked; successful cases verify the submitted port, readback, reboot through the old origin and navigation to the new origin. Rejected readback requests no reboot. Existing manual-upstream, two mode-save and fourteen status/layout browser scenarios also pass.

Candidate [lv-ue01-repeater-0eda26d6.uimage.bin](../../firmware/releases/lv-ue01-repeater-0eda26d6.uimage.bin), SHA256 `0eda26d6c2efe11018a8d611427d67553fe5bfd155e08b3efbeab53eaa436a8b`: image718108 bytes, compressed656243, container headroom52521. Independent hash/CRC/loader/decompression/resource/byte-scope verification passes. Relative to user-tested 69ce20ae, decoded changes are confined to controller storage and its response length. No native configuration handler, PHY or driver changes. Hardware persistence and reconnection remain unverified. User-tested69ce20ae and historical81db3776 are preserved; no live device access, upload or restart performed.

## Status correction — candidate 69ce20ae

User reports Disconnected while upstream connectivity works. Historical known-working captured status responses also contain `var ApCliConnStatus = ""`; empty text is not authoritative evidence of disconnection. The earlier 08323845 empty-to-disconnected mapping was incorrect and its synthetic browser test encoded the same bad assumption.

The original index renderer reads numeric state at `0x802551d0` (instructions `0x8000931c–0x80009330`); its template treats 2 as connected. The monitor uses the same state. The status renderer instead calls an ioctl-based string formatter at `0x8000ac68`, which can emit an empty string. A 24-byte read-only helper now exports the existing numeric state into that same inert status string using the native `%u` writer. The status-call patch is four bytes; its delay slot remains unchanged. Storage is zero retired-image space at main offset `0x19f340`, beyond startup-trace end `0x19f33c`. No driver state, configuration, DHCP, PHY or authentication code is changed by this correction.

The parser recognizes 2/Connected, 1, and 0/Disconnected as Connected, Connecting, and Disconnected respectively. Empty, absent or unknown values become Unavailable. Both displayed upstream lines use the same result. HTTP management access alone is not used as connection evidence.

Candidate: [lv-ue01-repeater-69ce20ae.uimage.bin](../../firmware/releases/lv-ue01-repeater-69ce20ae.uimage.bin), SHA256 `69ce20ae08603c7c2debd02ed6e3f468153f29f2afff8d3724d38feb11c6cedc`. Image718108, compressed656325, container headroom52439. Not flashed or hardware-verified. No fresh live response was obtained during this correction; the current management URL was requested. The known-working historical response disproves the previous parser assumption, but hardware validation of the new numeric export is still required.

Validation: 14 EN/ZH state/layout browser scenarios, manual-upstream regressions, two mode-save browser cases before the final parser-only tightening, and independent final-image integrity/resource/byte-scope checks passed. Two Unicorn tests check patch rejection and native-helper execution for state values 0/1/2/3/0xffffffff, unchanged A0/RA/SP/S0, expected formatter arguments and no helper memory writes. The status-template insertion offset was checked. Source tests and emulation are not proof of hardware association or DHCP forwarding. Temporary browsers/emulators exited.

## Earlier result — offline candidate 08323845

The management-page checklist below is complete. New candidate: [lv-ue01-hidden-ssid-08323845.uimage.bin](../../firmware/releases/lv-ue01-hidden-ssid-08323845.uimage.bin), SHA256 `08323845b16a147354cbba3230a370288b0be27381cea0cac0bf869ad1a5c599`. It is **not flashed, boot-tested, or a confirmed DHCP/Ethernet fix**. The preserved tested 81db3776 release is unchanged.

Overview now shows Upstream Wi-Fi alongside the detailed upstream-section state. A valid empty/non-connected association is Disconnected; unreadable/malformed status is Unavailable. The WPS note is removed in both languages. System file controls and account rows have scoped spacing changes. No new radio/DHCP/bridge/authentication behavior was introduced by this presentation follow-up; previous mode-switch changes remain included.

The HTML initially exceeded its fixed allocation by 46 bytes. Merging identical password-input CSS with the existing text/number-input rule reduced it to 10,503 bytes within the 10,552-byte allocation. No resource relocation or runtime DOM workaround was used. `build_ui_refresh.py` now updates bounded canonical HTML, controller data, and the three resource-response length locations while preserving existing callbacks and diagnostic payloads. `verify_ui_refresh.py` independently validates fixed allowed ranges, exact resource contents, container size, loader, hashes, CRCs, decompression and padding.

Image: 718,108 bytes; compressed stream: 656,220 bytes; container headroom: 52,544 bytes. This is compressed-container headroom, not a claim about unused physical Flash. Factory-default bytes remain unchanged from 81db3776; physical reset/blank-configuration provisioning remains unverified.

Validation passed: six EN/ZH status/layout scenarios; manual-upstream controller regressions; two EN/ZH mode-switch save/readback/reboot scenarios; eight scan checks against decoded candidate resources; four factory-default rendering/selection checks from the candidate. All browser requests were mocked and browser processes closed. Evidence: [08323845-test-readiness.json](08323845-test-readiness.json).

The following sections retain investigation history; 9875ca7c and 7d30631a are earlier candidates, not this final presentation build.

User reported clients failing to obtain addresses after switching modes and a visible extended SSID. No live configuration was read or changed for this review; the exact fault cause remains unconfirmed.

## Confirmed omission

The new controller imported SYS_WLMODE and upstream credentials but omitted WLN_APCLI_CONFIGED. In the original main, the wizard dispatcher compares WIZ_REP/WIZ_AP at 0x8000dcd0–0x8000dcf8 and writes config ID 0x04f20100 to string "1" at 0x8000dec8–0x8000ded4. That ID maps to WLN_APCLI_CONFIGED. The repeater monitor reads it at 0x8014e2dc and branches away from connection processing when zero at 0x8014e2f0–0x8014e2f4. The UI omission can matter for an unconfigured profile; a device already storing 1 would not be fixed by writing 1 again.

## Updated behavior

Both repeater save paths set the native configured flag, enable upstream Wi-Fi and disable the local DHCP server. Full save continues to enable upstream management and preserve the chosen management address; Connect retains the existing address and enables upstream management. LAN_IP_MODE remains 1. The previously problematic LAN DHCP-client path is not enabled.

Selecting repeater on a mode change defaults to hiding the extended SSID, with WPS off. Visibility remains editable. Connect applies that visibility and disables WPS when transitioning from AP; full save applies the displayed controls. Editing an already-running repeater with Connect leaves unrelated local settings unchanged. Switching to AP retains the existing DHCP-on default. Hiding SSID does not disable the radio or remove the local BSS.

The profile writer narrowly permits adding the registered configured flag if absent, and verifies it through the existing readback before reboot. Other missing configuration keys still fail closed. Native acceptance of adding the flag to an absent-field export has not been hardware-tested.

## Validation and limits

Manual-entry controller regressions pass. Four offline browser cases cover English/Chinese and Connect/full-save, an AP profile lacking the configured flag, submitted config, readback and reboot. All HTTP requests are mocked; Chrome closes afterward.

Candidate: firmware/releases/lv-ue01-hidden-ssid-9875ca7c.uimage.bin. Its sidecar records hashes and size. Only the controller and response-length stub differ from the preserved tested startup-trace image. No new driver/PHY changes, flash, reboot or physical factory reset occurred.

Upstream authentication, hidden-network discovery/channel handling, DHCP forwarding and actual mode-transition recovery still require hardware verification. Keeping the local DHCP server off requires a working upstream DHCP path; these changes do not guarantee client leases when association or forwarding fails. No confirmed Ethernet fix is claimed.

## Subsequent UI refinement

Mode changes now require the full Save & restart path. Upstream Connect & restart is disabled whenever the selected and saved modes differ, with bilingual guidance and a matching handler guard. It remains available for an already configured repeater. Two EN/ZH full-save browser cases verify the disabled button, guidance and configuration/readback/reboot flow; the controller regression verifies direct handler invocation cannot bypass the mode guard. This refinement was packaged in 7d30631a and retained in 08323845; candidate 9875ca7c predates it.

## Management-page refinement requirements

The page already polls `status.htm` and shows an upstream connection line in the Upstream Wi-Fi section. Add the same state to Overview as `Upstream Wi-Fi`. An explicit `Connected` driver result remains connected; a valid response with an empty or non-connected association result is disconnected, matching the vendor status page; an unreadable or malformed response is unavailable. Keep the detailed upstream-section line for configuration context.

Remove the WPS `Off by default.` note and its English/Chinese translation entry. Within the System form only, add vertical separation around the backup and firmware file inputs and use a larger consistent gap between the username, new-password and confirmation rows. These are presentation-only changes: they must not modify radio, DHCP, bridge, authentication, save, reboot or upgrade behavior.

Separate association evidence: this board exposes only 2.4 GHz channels 1--14, while the reported upstream hostapd network is 5 GHz/channel 36. The repeater cannot associate until it is given a compatible 2.4 GHz upstream network or replaced with dual-band hardware.

Offline browser coverage must exercise English and Chinese Connected, valid-empty/disconnected and malformed/unavailable status results, confirm the WPS note is absent, and assert the System-form spacing. Existing controller, browser, resource-layout, compression, CRC and byte-scope checks remain required. Any resulting candidate is offline only; flashing remains a separate explicit user decision.

Initial packaging attempt: the source regression passed, but the legacy builder stopped at the fixed dashboard allocation and the then-current release builder supported only JavaScript. That packaging limitation is resolved by 08323845 as described above. No AP action occurred.

### Implementation checklist

- [x] Add browser assertions first for the Overview upstream row, Connected/empty/malformed status states, absent WPS note, and System-form spacing in both locales; run them to confirm the current source fails the new contract.
- [x] In `logic/web-update/lan.htm`, add the Overview status row, remove the WPS note element, and scope file/account spacing rules to the System form.
- [x] In `logic/web-update/settings.js` and the generated minified controller, map a parseable non-connected status response to `Disconnected` and a parsing failure to `Unavailable`; remove the now-unused WPS translation entry.
- [x] Regenerate the controller, assemble the workspace, run the focused browser regression plus the existing manual-upstream, scan, factory-default, mode-switch, resource-layout and candidate integrity checks.
- [x] Build a new offline image only after the source and regression checks pass; record its hash and explicit not-flashed status. Do not upload, reboot, reset or otherwise alter the AP.
