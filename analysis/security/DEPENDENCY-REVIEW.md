# 固件依赖与更新可行性检查

检查日期：2026-10-18。对象：v28K.RPT.20220716，MT7628 家族，已导出前 1 MiB Flash 并通过主程序容器 CRC 与 LZMA 校验。以下为可从二进制确认的组件清单，不是完整 SBOM。

早期候选曾集成 jQuery 4.0.0；后续完整新界面已改用原生 JS 并移除 jQuery，保留 WPS 出厂默认关闭和旧图片清除。新候选及离线检查见 [网页更新说明](../web-update/README.md)。候选未刷入设备；驱动、系统、网络栈及 Bootloader 没有更新。

| 组件 | 发现与证据 | 更新判断 |
| --- | --- | --- |
| 无线驱动 | `4.1.0.0_CL150742`，版本字符串主程序偏移 0x16cfb8；邻近日期 Jul 16 2022；代码保留 os/ecos 驱动路径 | 需匹配 eCos 的厂商 SDK、板级配置和可构建源码，或确认为同一硬件版本的新版整包；不能直接用同芯片的 Linux 驱动二进制替换 |
| 操作系统 / SDK | Ralink-eCosAP 与 eCos 驱动路径已确认；具体 eCos 发行版、补丁级别未知 | 需要 SDK 配置、工具链及板级支持。字符串 V3.1.0.0 尚未完成归属，不当作 eCos 版本 |
| TCP/IP 网络栈 | socket/mbuf/路由 API 与 BSD 风格实现一致；具体来源、分支及版本未知 | 不给它猜测一个 FreeBSD/OpenBSD 版本，也不能直接替换为桌面 BSD 网络库；须先恢复来源与接口依赖 |
| DHCP / DNS / HTTP / Telnet | 可定位的固件内置实现，未发现可信独立版本标记 | 静态链接在主程序中；可继续定位具体逻辑并做补丁，整体更新依赖 SDK/源码 |
| Bootloader | U-Boot 1.1.3，Aug 7 2016，来自启动区 0x12e50 | 上游已有 v2026.10；本板是否受支持未知，不能直接刷上游通用镜像。需要 DDR、SPI、分区、校准及恢复流程验证；升级它本身不能证明改善运行时 AirPlay |
| Web jQuery | 1.11.1，主程序偏移 0x1ad83c，提取的 JS 95785 字节 | 最明确的可替换依赖。官方现有 4.0.0 和 3.7.1；替换后须验证所有配置流程及固件重新封装 |
| LZMA | 主程序压缩格式和解压器已确认；实现版本未知 | 不能从使用 LZMA 格式推断安装了某个版本的 xz/liblzma，更不能直接套用其版本漏洞 |
| 密码学 / MCU 微码 | 有无线安全及微码版本日志，库来源和对应微码版本未完全识别 | 不将未识别的实现标为 OpenSSL/mbedTLS，也不随意匹配 CVE；需进一步识别函数、常量和固件 blob |

原始版本证据：`component-strings.json`。当前没有确认该具体设备的品牌、型号、硬件版本和完整 Flash/RAM 容量，尚未找到可以认定兼容的官方新版整包；已向用户询问标签信息。没有向设备写入任何候选固件或更新依赖。

## jQuery 安全性与兼容性

1.11.1 落在维护者公布的 CVE-2020-11022 与 CVE-2020-11023 版本范围内。这些公告针对将不可信 HTML 传入特定 DOM 方法的情形；仅凭版本不能断言本设备存在已验证的可利用路径。[维护者公告 11022](https://github.com/jquery/jquery/security/advisories/GHSA-gxr4-xjj5-5px2)、[维护者公告 11023](https://github.com/jquery/jquery/security/advisories/GHSA-jpcq-cgw6-v4j6)。

已从官方 CDN 下载 3.7.1（87533 字节）和 4.0.0（78748 字节），均小于原 JS 文本区域；可以进一步研究保持原区域长度和后续地址不变的替换方案。但文本放得下不代表网页兼容、压缩后镜像可用或设备可升级。版本和哈希见 `jquery-artifacts.json`。[官方发布列表](https://releases.jquery.com/)。

4.0.0 是此次检查时的最新主要版本，含不兼容变更；可先用 3.7.1 验证较小的迁移跨度，再评估 4.0.0，或直接对 4.0.0 完成完整页面测试后选用。静态扫描没有在自定义脚本/模板中匹配到列出的部分旧 API（size、andSelf、browser、live、die、success/error/complete、bind/unbind/load 的调用签名），发现 16 个 html 调用；这些签名检查不足以证明兼容或漏洞可达。[4.0 发布说明](https://blog.jquery.com/2026/01/17/jquery-4-0-0/)、[升级指南](https://jquery.com/upgrade-guide/4.0/)。

jQuery 更新主要影响管理网页，不据此承诺改善无线转发、DHCP 启动时序或 X99 丢包。后者优先检查无线驱动、MAT/ARP/DHCP 和上游连接恢复路径。

## WPS 默认关闭候选

当前设备已回读 WLN_WscConfMode=0，之前的正常重启后仍为 0。原始固件的出厂默认值却是 `WLN_WscConfMode=7`，因此需要区分“当前配置关闭”与“恢复出厂默认关闭”。

`build_wps_default_candidate.py` 已构建离线候选，仅修改解压主程序 0x19e1a5 一个字节，把默认字符串中的 7 改为 0。LZMA 重新压缩为 708526 字节，放入原有 708764 字节区域；主程序长度、加载器前缀、载荷长度保持不变，填充余量并重算 uImage 两项 CRC。已验证解压往返和 CRC。

产物 `wps-default-off.uimage.NOT-FOR-FLASHING.bin` 是**离线分析候选**，不是已批准或经过设备验证的升级包。它不改变已有 NVRAM 配置，不修改实体按键或运行时重新启用 WPS 的代码路径；尚未验证升级格式、板型接受、恢复出厂行为及实体按键。没有刷入设备。证据及 SHA256 见 `wps-default-candidate.json`。

## 后续更新所需条件

SSID 隐藏已由用户扫描确认，X99/mDNS 长期测试由用户进行。无线功能、性能与稳定性候选见 [无线功能审查](WIRELESS-FEATURE-REVIEW.md)：已从二进制确认发射功率、自动选信道、20/40 MHz、WMM 等配置与部分驱动入口；尚未实测新参数效果，没有改动正在长期测试的设备。

待设备型号/硬件版本确认后，查厂商官方固件与 GPL/SDK 发布；再确定整包升级还是受控的小范围补丁。构建源码不可得时，不能把无线驱动和网络栈的“换新版”当作可直接完成的依赖安装任务。

[U-Boot 官方发布记录](https://docs.u-boot.org/en/latest/develop/release_cycle.html)确认 v2026.10 于 2026-10-05 发布。[eCos 官方安装页](https://www.ecos.sourceware.org/getstart.html)和[网络栈说明](https://www.ecos.sourceware.org/docs-latest/ref/net-common-tcpip.html)提供上游信息，但不能据此推断本固件的具体版本或可直接移植。
