# PIX-LINK LV-UE01 firmware analysis / 固件分析

Analysis, management UI patches and PHY startup diagnostics for the photographed LV-UE01-V1.0 board (MediaTek MT7628KN), based on vendor firmware `v28K.RPT.20220716`. This is a binary patch workflow, not a rebuild of the vendor OS or network drivers.

The currently tested build is **81db3776**, SHA256 `81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377`. On 2026-10-23 the tester reported almost two days without the previous Ethernet interruption and plans to continue testing. This is a user observation, not proof that the intermittent problem is fixed. The PHY reset behavior is unchanged; this build adds diagnostics.

## Layout

| Directory | Contents |
| --- | --- |
| `analysis/` | Sanitized reports, disassembly, manifests and experiment summaries; older results retain their historical scope. |
| `logic/` | Python analysis/build/test tools, management HTML/JavaScript and the MIPS diagnostic assembler. |
| `firmware/releases/` | The exact tested uImage; see its SHA256 and the reset limitations below. |
| `firmware/original/` | Extracted original program inputs; these are not full-device backups. |
| `firmware/intermediates/` | Historical candidates and raw main/payload files used by offline regression tests. Files marked NOT-FLASHABLE are not upgrade images. |
| `.private/` | Local original workbench: complete Flash backups, captured configuration, raw fault evidence and history. Git ignores this directory. It is not part of the public repository. |
| `.work/` | Generated disposable workspace restoring the original relative paths expected by the tools. Git ignores it. |

Published copies remove known saved Wi-Fi values, captured authorization tokens and known device MACs. The untouched local snapshot and migration hash index stay under `.private/`. Preparing this repository does not publish it or upload anything to GitHub.

## Initialization and factory reset

**Physical factory reset has not been tested on the new build.** Offline rendering with its embedded factory defaults passes in English and Chinese; this is not a native first-boot test. Normal upgrade/reboot and preservation of the existing repeater settings have been verified. No reset was performed during the long-term test.

Embedded factory defaults retain vendor **AP mode**, DHCP server **on**, fixed LAN address **192.168.10.1**, and upstream management **off** (its saved port is 8080). WPS is patched **off**. Local SSID visibility, open Wi-Fi security and the vendor administration credentials are otherwise unchanged. These are binary/default-table findings, not a verified first-boot provisioning test.

When the new UI saves repeater settings it disables the local DHCP server and enables upstream management. Merely loading the UI does not save those changes. After factory reset, saved upstream credentials and the current hidden-SSID configuration should not be assumed to remain. A reset is not a firmware downgrade.

See [initialization/reset review](analysis/reviews/INITIALIZATION-RESET-REVIEW.md) and [exact default evidence](analysis/reviews/factory-default-review.json). The stock version string is unchanged; identify the build by artifact hash and diagnostic behavior.

## Offline checks

Use Python 3.9+ and Node.js available on PATH. Chrome is needed only for browser checks. Python and Node dependencies are pinned; no `/tmp` dependency directory is required.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm install --ignore-scripts --no-audit --no-fund
.venv/bin/python tools/prepare_workspace.py
(cd .work/phy-diagnostic && ../../.venv/bin/python -m unittest test_patch test_original_baseline test_combined_candidate test_startup_trace)
.venv/bin/python .work/phy-diagnostic/verify_startup_trace.py
node .work/web-update/test_scan_browser.cjs
node .work/web-update/test_factory_defaults.cjs
```

Edit files in `logic/`, then run `tools/prepare_workspace.py` again before testing. Generated outputs stay in `.work/`; rebuilding does not replace the checked-in tested release automatically. `workspace-map.json` records historical-to-current paths and binary hashes. The initial migration changed paths/tool portability, not the shipped firmware bytes.

`--include-private` restores local captures into the ignored workspace for private backup checks; those checks cannot run on a public clone without the captured inputs. Live capture/install/rollback scripts are historical device-specific tooling, require a separate explicit device action and local credentials/identity, and are not run by these offline checks. The speed-path audit also needs the original external `esw_rt3050-upstream.c` reference, which is not bundled if its old temporary copy is unavailable.

## 中文说明

- 分开保存分析资料、逻辑代码和固件，原始含隐私的数据完整保存在 Git 忽略的 `.private/`。
- 本次只整理本地目录，没有提交、推送或发布 GitHub Release。
- 新版目前仍是诊断测试版，没有升级原厂内核、驱动或网络栈，也没有确认修复长期断连。
- 初始化/恢复出厂尚未完全验证。恢复出厂会回到 AP 默认配置；中继 DHCP 关闭、上游管理启用由新页面保存时设置。默认本地 Wi-Fi 仍是开放且可见，不能把现有隐藏/加密配置当作固件出厂默认值。
- 不为本次整理重启或重置正在长期测试的设备。原始 Flash、校准区和配置备份不属于公开升级文件。

## Continuing this project

Read [MEMORY.md](MEMORY.md) and [AGENTS.md](AGENTS.md) when resuming. Device/evidence details stay in the ignored `.private/PROJECT-MEMORY.md`. The former ESP32 `firmware-analysis` directory and compatibility link have been removed. Original archived paths are left as historical records; `tools/prepare_workspace.py --include-private` rebases runtime JSON paths to `.work/` and preserves local private installation records. If a workspace already contains private evidence, keep using `--include-private`; the public-only mode will refuse to relabel it.
