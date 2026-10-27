# Flash backup and recovery readiness

**已完成标称 2 MiB 地址窗口的双份只读备份，独立校验通过；恢复入口仍未实测，诊断候选继续保留 NOT-FOR-FLASHING。** 本轮仅登录、必要时进入 OS 菜单并运行 `spi rd`，没有写 Flash、擦除、重启或修改配置。采集进程已退出，连接均已关闭。

## 完成结果

- 两份文件各 2,097,152 字节，128 个 16 KiB 块分别双读一致，整份文件逐字节一致。
- 整份 SHA256：`b3413627600d69787c731355827d633bee30407062886df0fc7489d6aa704f9a`。
- 独立验证器重新核对全部块、整份文件、文件权限以及原固件 uImage 的头部/载荷 CRC。
- 内含原固件 uImage 为 718,108 字节，SHA256 `43ef36588e9f3c08b302583a60fc30bcb8fd374953a82a88eb64fcef2714c243`，与此前导出完全相同。
- 前 0x30000 字节与旧备份一致；前 1 MiB 整体有 9,976 字节不同，未将这些差异全部归因为配置变化。后 1 MiB 全为 FF。
- 20 项离线/本机回环测试通过；独立代码审查已完成。诊断候选离线制品验证也通过，候选没有刷入。

独立结果见 [full-backup-verification.json](full-backup-verification.json)，测试结果见 [test-results.json](test-results.json)，恢复分析见 [recovery-evidence.json](recovery-evidence.json)。原始文件为 `private-captures/full-2m-readonly-nc/flash-2m-copy0.bin` 和 `flash-2m-copy1.bin`，目录权限 0700、文件 0600，可能含配置、凭据和校准数据，不公开分发。**原始 Flash 备份不是可上传到 Web 升级页面的固件包。** 旧 `flash.bin` 仍保留为原来的 1 MiB 历史文件。

## 接收可靠性与验收

此前使用 curl 的本机接收链路，在不连接 AP 的回环测试中也能复现首 9 字节后停滞。现改用持续 nc 会话，本机分包/连续读取测试和整片采集均完成；该结果不等于确认 AP 的掉线根因。

控制台仍会混入日志或损坏十六进制词，包括格式合法但数值错误的词。工具采用 1 KiB 请求，无法映射时细分；坏行单独双读；每个完整块必须有两份完全一致的数据。响应超时最多重连重读一次；块不一致时保留被拒副本，最多重新获取一轮完整双副本。不会截断坏词、删除混入的日志、猜值或多数拼接。达到上限则标记 INCOMPLETE 并保留已验证进度。此前失败记录仍保留，不能当作完整备份使用。

这是顺序分块采集，不是原子快照；没有全芯片厂商校验和。照片芯片标称 2 MiB，读取窗口也是 0x200000，但运行时 JEDEC ID 尚未读取，不能声称独立确认了芯片容量或型号。备份成功也不代表恢复可用或诊断候选可启动。

## 恢复与 RAM 试启动路径

旧备份中的 U-Boot 明确区分：

| 菜单 | 固件中的描述 |
|---|---|
| 1 | Load system code to SDRAM via TFTP |
| 2 | Load system code then write to Flash via TFTP |
| 3 | Boot system code via Flash (default) |

命令表还存在 `tftpboot`、`bootm`、`saveenv`，表地址与入口见机器可读证据。后续已核实两个具体副作用：启动 GPIO 的 Upgrade Mode 路径会调用固件写入及 0x30000..0x3ffff 擦除；菜单 1 的 TFTP/RAM 自动启动在参数更改标志非零时调用与 saveenv 相同的环境保存后端。五组原始分支实验通过，实机未测试。详见 [启动入口复核](BOOT-ENTRY-REVIEW.md)。尚未验证如何可控进入、板上串口针序和电平、TFTP 实际参数或候选启动行为，因此不提供可直接执行的按键/刷写步骤，也不将“加载 RAM”作为已经验证无 Flash 写入的完整流程。

编译默认字符串包含 baudrate=57600、bootdelay=2；它们不是本机当前环境测量值，不能直接作为接线或启动设置。四个焊盘的功能/针序仍未验证。

用户已明确没有 USB 转 TTL 适配器和万用表。现有条件下无法验证串口入口，也没有已证实的软件方式进入该 RAM 菜单。后续实机阶段需要先取得可验证的控制台/恢复入口；此前保留当前原固件和已恢复的 20/40 MHz 配置，不刷入诊断候选。

## 离线复核

```sh
python3 firmware-analysis/ap-192.168.1.2/recovery/verify_full.py
python3 firmware-analysis/ap-192.168.1.2/recovery/analyze_recovery.py
python3 firmware-analysis/ap-192.168.1.2/recovery/run_tests.py --loopback
```

上述命令不访问 AP；最后一条仅为测试建立本机回环连接。实际采集工具仍是针对本设备的取证工具，不是已验证的通用恢复工具。

## 回滚范围补充核对

原版/候选容器及备份的离线替换、回滚演算已完成。假设 4 KiB 或 64 KiB 对齐均覆盖 0x50000..0x100000，镜像后有 2,788 字节尾部。另建模启动升级路径的环境区擦除后，仅回滚原 uImage 仍留下 6,506 字节差异；还需考虑镜像外的环境状态，不能将完整备份等同于已有可靠恢复方式。未访问设备。见 [回滚范围复核](ROLLBACK-LAYOUT-REVIEW.md)。

## 网络控制台核查

原初始化代码仅注册 serial，原 getc/tstc 分发在四组建模场景中均走 UART；本轮没有建立网络控制 U-Boot 菜单的途径。见 [控制台核查](BOOT-CONSOLE-REVIEW.md)。这是已检查代码路径的结论，串口或网络恢复均未实测，不能据此刷入候选。

## 手动加载命令与后续决策

18 组原 TFTP 命令离线模型确认：autostart 缺失/no 时不进入保存或自动启动路径；零长度网络返回仍可返回命令成功。该结果仅支持后续串口条件下验证手动流程，不是已有安全启动入口。下一项用户决策及各阶段边界见 [手动 RAM 验证准备](MANUAL-RAM-READINESS.md)。

## 升级失败处理核查

新增四组原始代码离线实验确认：NetLoop 返回 -1 时，tftpboot 返回失败值 1，但 Upgrade Mode 调用者仍调用固件写入和 0x30000 区块擦除；写入后端返回错误也不阻止后续擦除调用。因此不采用“只进入升级、不提供文件”的实机探测。下载失败具体是否返回而非持续重试、实际 Flash 后端行为均未验证。见 [启动入口复核](BOOT-ENTRY-REVIEW.md) 与 [实验结果](boot-failure-experiment.json)。没有 AP 访问或写操作。
