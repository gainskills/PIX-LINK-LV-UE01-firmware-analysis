# Updated UI/security with working PHY diagnostics

**Installed with explicit user approval, 2026-10-22 UTC 03:59.** The AP now runs this redesigned UI/security + PHY diagnostic image (`c2948bec…`). Live resource/authentication/configuration checks, six PHY reads, and browser login/locale/layout passed. X99 physical link down was captured after the upgrade reboot; it is not a connectivity-fix result. The user was asked to power-cycle X99 only after preserving that fault state. See [actual deployment and limitations](../../deployment/README.md).

This build combines the previously tested redesigned UI/security image (`481ed957…`) with the working diagnostic payload and actual Telnet builtin-dispatch fix. It does not change Ethernet recovery behavior or upgrade the driver/network stack. The scan warning remains as the user requested. Earlier offline reports retain their creation-time “not installed” labels.

| Property | Combined candidate |
| --- | --- |
| uImage SHA256 | c2948bec9931d02837ccfe09b5f53aaf55b4e4cd00c1e6060c310f48a68b175a |
| uImage / decompressed main | 718,108 / 2,174,360 bytes |
| Compressed stream / remaining padding | 655,726 / 53,038 bytes |
| Difference from secure UI main | 499 bytes within four diagnostic ranges |
| UI and authentication | Preserved byte-for-byte outside those four ranges |

Four integration tests were added for range preservation, actual Telnet builtin execution and rejection of changed/obsolete inputs. The complete 26-test PHY suite passes. The combined bytes also pass the existing 20 authentication and 20 pre-body POST authorization cases. Independent artifact verification checks source/output fingerprints, both CRCs, original loader/header, bounded LZMA decompression, exact padding, modified ranges and equality to the working diagnostic bytes. These are offline checks; they do not validate combined startup, actual MDIO timing or hardware recovery.

## Wi-Fi scan finding

The current UI asks **“Scan nearby networks? Wi-Fi may be briefly interrupted.”** Accepting this confirmation requests `live_get_site_survey.htm`; canceling it sends no request. Scanning is enabled for upstream selection in repeater mode; that upstream control is disabled in AP mode. Selecting a scan result changes the form only; Connect applies the selected network separately.

An offline Playwright test uses the actual HTML and JS extracted/checked against the combined image with a mock backend. Eight English/Chinese checks pass: cancel/no request, accept/results/selection/no save, failure with retry, AP-mode disabling. It did not reproduce a UI scan block. The user's exact warning/error is still requested; no claim that the reported live behavior is fixed. No real AP scan was triggered, since scanning can interrupt its shared radio.

## Next installation and test

Installation is complete; source images and earlier deployment records are retained. Current configuration is unchanged. The fault collector now selects this combined SHA and its new installation record; eight offline parser/selection tests pass and a complete real fault capture succeeded. It never falls back to the old baseline after a newer upload. The first post-flash baseline is a fault state (link down/X99 HTTP timeout), not a healthy starting point; await the requested X99-only power cycle to establish recovery without changing the AP.

Hardware recovery remains unverified. A short successful test is not an Ethernet fix or long-term stability result. Long-term testing remains with the user; fault capture happens when they notify us.

Evidence: [manifest](build-manifest.json), [independent verification](verification-results.json), [test summary](test-summary.json), [scan browser results](scan-browser-results.json).
