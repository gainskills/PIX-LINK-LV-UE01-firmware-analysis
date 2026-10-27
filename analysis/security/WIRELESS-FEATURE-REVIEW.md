# Wireless features and stability review

Reviewed 2026-10-18, offline, against v28K.RPT.20220716. No AP queries, config writes, scans, restarts or firmware installation were performed. X99/mDNS long-term testing remains with the user.

## Management ports

The LAN listener is hardcoded to HTTP 80: `http://192.168.10.1/` when that static LAN address is enabled. The upstream listener uses SYS_RM_PORT, default 8080: `http://192.168.1.2:8080/` with the current upstream lease. The independent listeners and interface address checks are in `../ssid-airplay/http-management-bind.txt`, particularly 0x800110f8 loading 0x50 (80). The new UI accurately describes these separate addresses. The preview's 127.0.0.1:8765 is neither device address nor device port.

## Findings and proposed controls

These are existing firmware capabilities that could be exposed in the new UI. They are not features introduced by upgrading jQuery. Binary presence and a saved config value do not establish runtime behavior or performance improvement.

| Feature | Local evidence | Proposed behavior and limits |
| --- | --- | --- |
| Transmit power | WLN_TxPower, config 0x04120100; factory and saved value 100; TxPower setter 0x80082c5c | Offer 25/50/75/100% in Advanced, preserving current value by default. The setter compares against 101 and logs TxPowerPercentage. This is a percentage setting, not measured dBm or a calibrated linear wattage scale. Do not offer values above 100. It is a radio setting; changes can affect upstream connectivity as well as the extended network. No evidence supports independently reducing only the extended SSID's power. |
| AP channel, manual or Auto | WLN_Channel 0x04070100; WLN_AutoChannelSelect 0x04370100. Existing serializer maps Auto to channel=0, selection=3; manual to selection=0. Driver includes AutoChannelAtBootup logging | In AP mode offer Auto/manual using the firmware's existing region/channel table. In repeater mode display “Follow upstream”, plus the actual channel if runtime telemetry can be recovered. Do not let ACS choose a separate backhaul channel. The numeric algorithm's scoring and continuous rescan behavior have not been established. Do not interpret the runtime AutoChannelSel command as equivalent to the persisted numeric selection flag. |
| Channel width | WLN_HT_BW 0x04410100, factory/saved 1; HtBw setter 0x8007ef04 accepts 0/1; driver includes 20/40 MHz configuration and AP-client fallback paths | Offer 20 MHz and the existing 40 MHz-capable mode in AP mode. Evaluate 20 MHz as a stability candidate. Repeater width is constrained by the upstream association and driver negotiation: a requested config value is not proof of effective width. Show configured and effective width separately when available. |
| WMM | WLN_WmmCapable 0x04540200; factory/saved 0; WmmCapable setter 0x80036f38 | Worth verifying first, then exposing as an advanced control. The exported field is BSS-related and must retain the firmware's per-BSS representation. A stored 0 does not prove upstream QoS is off, nor that the HT path does not enable WMM internally. Do not promise an AirPlay fix or change all BSS values together. |
| 20/40 MHz coexistence | WLN_HT_BSSCoexistence 0x04e40100, factory/saved 0; HtBssCoex setter 0x8007a0b8 | Secondary candidate when retaining 40 MHz operation. Needs effective-width and reconnect validation in this driver. Keep explicit 20 MHz testing separate so cause and effect remain observable. |
| Power saving | WLN_APSDCapable 0x04550200, factory/saved 0; driver also mentions ApCliAPSDCapable | Keep the saved AP-side value initially. AP-side APSD and upstream client power saving are separate; do not label one switch as controlling both. No verified upstream client power-saving toggle has been recovered in this review. |
| Beacon / DTIM | WLN_BeaconPeriod=100; WLN_DtimPeriod=1; setters 0x80042bb8 / 0x8003538c | Preserve initially. Changing multicast delivery timing is not a general stability fix. Do not add a collection of tuning controls without a measured problem. |
| TxBurst / proprietary aggregation | Saved TxBurst=1 and PktAggregate=0 | Preserve initially. Neither is established as a universal performance improvement; do not automatically enable aggregation or call it an optimization preset. |

The stored values above come from `../ssid-airplay/longrun/verified-reboot-profile.bin`, not a new live read. In that saved profile channel=9 and AutoChannelSelect=0. A configured channel is not proof of the current associated channel.

For general guidance, Apple recommends 20 MHz on 2.4 GHz and WMM enabled; these are useful test directions, not proof of this device's implementation or a diagnosis of X99. [Apple router settings](https://support.apple.com/en-us/102766).

The chipset family is an 802.11n router/repeater platform. The single-radio repeater design requires upstream channel alignment; do not offer independent channel optimization while associated. [MediaTek platform](https://www.mediatek.com/products/home-networking/mt7628k-n-a), [Cisco repeater channel behavior](https://www.cisco.com/en/US/docs/wireless/access_point/350/configuration/guide/ap35ch12_ps458_TSD_Products_Configuration_Guide_Chapter.html). The application to this board is based on the recovered MT7628 identity, shared-radio configuration and AP-client code; this review did not inspect the physical board.

## Highest-value additions

1. **Connection diagnostics:** configured/effective channel and width, upstream association, RSSI, management IP, uptime and reconnect count. Driver strings confirm RSSI, retry, failed-ACK and CRC counters exist; their read API and stable backend representation still need recovery. Prefer counters over repeated active scans. This adds visibility without guessing a beneficial radio setting.
2. **Mode-aware radio settings:** transmit power; AP-only Auto/manual channel and width; repeater “Follow upstream”. Keep advanced fields collapsed and translated. Read back saved values and distinguish them from negotiated values.
3. **Controlled stability trials:** compare 20 MHz with the existing width configuration and investigate effective WMM. Change one setting at a time; do not combine them into an unverified “stable” preset. Keep current live defaults during the user's long-term run.
4. **Safe apply/recovery, later:** an actual device-side confirmation/rollback timer would be useful for radio changes. A browser timeout cannot restore an unreachable device. This needs an eCos-side implementation and verified NVRAM/recovery behavior. Avoid periodic forced reboots or aggressive scan/reconnect loops.

## Dependency implications and feasibility

The early offline candidate contained jQuery 4.0.0; the later complete management UI now removes jQuery and uses native JavaScript, but wireless driver 4.1.0.0_CL150742, eCos and the network stack are unchanged. Updating browser JavaScript does not update the radio, bridge or DHCP implementation. Driver/network-stack upgrades require a compatible vendor SDK/build or a verified exact-board firmware image; no compatible replacement has been established. Model/board information remains unconfirmed.

The new controller already uses native browser APIs. Since old UI compatibility is no longer a requirement, the later complete UI has removed jQuery and reduced browser download/parse work, including a native login page. Removing the shared bundle before moving all entry pages would leave the original landing/navigation routes incomplete. Also, shrinking a resource inside the currently fixed-size decompressed image does not establish reduced AP RAM use or improved packet forwarding.

At the time of this review the candidate’s compressed stream was 708533 / 708764 bytes (**231 bytes headroom**). A later image-removal build reduced it to 673430 bytes (**35334 bytes headroom**); the subsequent complete native UI is 655421 bytes (**53343 bytes headroom**). See `../web-update/README.md`. The image-removal build demonstrates useful capacity recovery without relocating resources. Future controls must still be checked against the updated compressed budget on each build. This is a size constraint, not a reason to change loader addresses without validation. The existing candidate was not changed by this review.

No evidence here establishes support for WPA3, 802.11k/v/r roaming, 5 GHz operation, enterprise automatic RF management or a generic Linux-driver swap. Those are not promised as web-only additions.

## Evidence and reproducibility

`review_wireless_features.py` reads the decompressed binary and a whitelist of non-secret radio fields from the saved profile. It records name offsets, numeric config IDs, factory defaults, saved values and command-table function addresses in `wireless-feature-evidence.json`, with setter windows in `wireless-feature-disassembly.txt`. It uses the existing temporary Capstone installation; it never contacts the device.

Main binary SHA256: 2ad2bd309b2f83594b34f90b4547d6d7e8af1c2b410ce499086758ca9a4923fe. No firmware candidate, dependency or live configuration was updated in this review.
