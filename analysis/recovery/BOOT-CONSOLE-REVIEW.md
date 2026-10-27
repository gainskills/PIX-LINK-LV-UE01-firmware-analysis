# U-Boot 网络控制台可行性核查

本轮只分析本机启动区并运行本地机器码实验，没有访问 AP、连接串口、重启或刷写。

## 结论

**已检查的初始化路径仅注册 serial；启动菜单的输入最终走 UART。没有建立可通过网络选择 RAM 菜单的途径。** 这不是对所有动态路径不存在性的证明，但目前没有依据让用户通过 Telnet、HTTP 或 TFTP 控制这个 U-Boot 菜单。

TFTP 是该固件的镜像传输路径，不能仅因它存在就当作网络控制台。运行时 eCos 的 Telnet 与启动时 U-Boot 的菜单输入也是不同接口。

## 原始代码与实验

设备注册初始化 0xbc00e464 构造一个 0x34 字节记录，名为 serial，标志 0x80000003，并调用 0xbc00e420 的注册包装函数。原始函数实验截取记录，确认：

| 回调 | 地址 |
| --- | --- |
| putc | 0xbc01231c |
| puts | 0xbc0123a8 |
| tstc | 0xbc012370 |
| getc | 0xbc012384 |

在本次已解码代码范围的 GP 相对注册包装函数引用扫描中，只有该初始化调用点。字符串调查也只找到 serial/stdin/stdout/stderr，没有 netconsole/ncip 注册线索；字符串缺失本身不作为“不存在”的证明。

菜单轮询/读取经 0xbc00df34、0xbc00def4 分发。分别模拟 stdio 尚未初始化、stdio 已初始化并指向上述原函数生成的 serial 记录，共四组原始分发实验，全部进入 UART 回调。UART 代码实际读取状态寄存器 0xb0000c14，字符读取 0xb0000c00；没有在这些回调内进入以太网接收函数。

原设备初始化加四组分发实验通过，见 boot-console-experiment.json。实验替代内存分配、注册表插入和 UART 回调，不操作真实硬件；已初始化场景显式使用原初始化生成的 serial 记录，未宣称仿真全部设备选择过程。反汇编见 console-init-disassembly.txt、console-device-registration-disassembly.txt。

## 当前可执行边界

- 标称 2 MiB 双份备份及离线诊断候选已有校验结果。
- 原终端 reg 不能直接访问 RAM，尚无已验证的软件注入或原生 PHY 查询入口。
- GPIO Upgrade Mode 会写固件/擦除；RAM 菜单自动启动有条件保存环境，见 BOOT-ENTRY-REVIEW.md。
- 本轮没有找到可替代串口控制的网络入口。串口针序、电平、控制台交互和可控 RAM 试启动仍未实测；用户此前说明没有串口适配器和万用表，不重复要求已有这些设备。

因此，继续分析静态分支可以审查候选，但无法补足故障现场的 BMCR/BMSR 或证明候选能启动。当前不刷入候选，也不触发按键升级。

复现：`python3 firmware-analysis/ap-192.168.1.2/recovery/emulate_boot_console.py`。依赖本机已有 Unicorn，当前主机需在沙箱外初始化；脚本没有网络或串口访问。
