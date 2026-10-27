# AP management restoration implementation plan

**Goal:** Restore the missing management functions in the new bilingual, image-free interface while adding editable extended SSID and MAC-based default names.

**Architecture:** Keep the original firmware backend and resource layout. Serve a larger canonical dashboard from the index resource; make the LAN callback reference that resource without moving any other addresses. Native browser JS handles forms. Read existing status responses as inert text through a strict adapter, never execute their scripts or load their images. Reuse verified profile import/export and existing reboot/upgrade endpoints. Do not touch the live AP.

**Scope:** User requests: status (mode/radio/upstream/channel/security/clients), firmware version/uptime, AP/repeater configuration, power, 20/40 MHz, Wi-Fi and administrator passwords, backup/restore/reload, upgrade, reboot, custom extended SSID and upstream SSID + own device MAC default. Chinese/English follow browser locale. Existing custom names remain until explicitly changed. SSIDs must fit 32 UTF-8 bytes; preserve the 13-byte MAC suffix and truncate upstream prefix by code point.

## Constraints and review focus

- Preserve main length, loader prefix, all resource-table positions and original image allocation. Enforce LZMA limit and CRC/round-trip checks on every build.
- Device status can be missing or malformed; show unavailable, never fabricated runtime values. Never select a parent BSSID as the device MAC.
- Preserve unchanged credentials and BSS2–4; passwords are never inserted into HTML or logs.
- Reject invalid config uploads, firmware candidates explicitly marked NOT-FOR-FLASHING and invalid image size/CRC before upload. An upload response is not proof of a successful upgrade.
- Changing radio/mode or restoring another profile may remove current connectivity; require an explicit action and retain endpoint guards. No scheduled scans or AP changes during user long-term testing.

## Implementation tasks (native execution)

- [x] Add failing browser checks for extended SSID, byte-safe generated names, full dashboard controls and status parsing.
- [x] Restore UI with status, wireless setup, advanced management, account and system tools. Extend translated labels and messages. Implement state/validation/config import and action protocols; mock actual request formats.
- [x] Expand canonical index resource and LAN alias callback with independent binary verification. Preserve runtime status backend. Rebuild and verify bounds, unchanged bytes, CRCs and decompression.
- [x] Run new UI regression, locale/mobile tests, import/password/mode/radio/upload/reboot mocks and final size verification. Document limits and candidate status. Keep original firmware and AP unmodified.

**Validation commands:** `python3 firmware-analysis/ap-192.168.1.2/web-update/build.py`; `python3 firmware-analysis/ap-192.168.1.2/web-update/verify.py`; temporary Playwright scripts under `/private/tmp/keyauto-ap-web-tools`.

No git repository exists at the task root; changes are kept in the authorized workspace and verified directly. No sub-agents or live flash actions are used.

Completed offline: 19 baseline checks, 15 dashboard flows, 13 maintenance flows and four browser-locale flows passed. Native header/login, no duplicate top mode, grouped Local Wi-Fi controls and concise bilingual wording verified. Final compressed stream 654381 bytes / 708764 budget; headroom 54383 bytes. No device modifications.
