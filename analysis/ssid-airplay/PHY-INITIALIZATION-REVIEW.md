# 仅针对 LV-UE01 的 PHY 初始化复核

用户明确没有交换机，只关注本设备排查。因此后续不以新增硬件对照为前置条件。本轮仅离线分析，无设备配置、PHY、MDIO 或固件写入。

## 已复核的初始化序列

`compare_phy_init.py` 对本机 0x80015a88..0x80015c98 的受限指令集做离线参数求值，包括循环和延迟槽，提取 85 次 PHY 写与 5 次 PHY 读；遇到未支持指令即失败，不对任意函数做猜测执行。不是完整硬件仿真，也不证明实际启动时该函数已执行。原固件 SHA 和全部调用地址记录在 `phy-init-comparison.json`。

参照 [OpenWrt 官方 esw_rt3050.c](https://raw.githubusercontent.com/openwrt/openwrt/main/target/linux/ramips/files/drivers/net/ethernet/ralink/esw_rt3050.c) 的 MT7628AN/MT7688 分支，解析到 70 次写，下载内容 SHA 也已保存。这不是 LV-UE01 MT7628KN 的匹配 SDK，不能直接把它搬入本机。

### 相同项

末尾 13 次 100Base AOI 模拟参数设置逐项一致，包含 G5 页选择及寄存器 19–30 的值。不存在依据这组对照就声称本机模拟参数全错的理由。

### 差异项

| 项目 | 本机初始化 | 参照分支 | 当前含义 |
| --- | --- | --- | --- |
| 初始 G2 寄存器 26 | 0 | 0x20 | 私有寄存器差异，位定义未充分确认 |
| 每个 PHY 的标准控制寄存器 0 | 0x3300 | 0x3100 | 本机还请求自动协商重启；不是强制关闭协商 |
| 每 PHY 额外 MMD 序列 | 13=7, 14=0x3c, 13=0x4007, 14=0 | 该分支无这组写入 | 本机有清除 EEE advertisement 的初始化意图 |
| 每 PHY advertisement | 读寄存器 4 后 OR 0x400 | 该分支无此操作 | 本机额外设置 PAUSE advertisement 位 |
| 每 PHY 循环尾部 G2 处理 | 未出现相同的 G2/26 清零序列 | 31=0x2000，26=0 | 页选择和私有初始化时序不同，尚不能定为缺陷 |

EEE 解释参考 [Linux MDIO 定义](https://raw.githubusercontent.com/torvalds/linux/master/include/uapi/linux/mdio.h)：MMD 7 为自动协商，寄存器 60（0x3c）为 EEE advertisement。仅证明代码意图，未读取本机当前 MMD 实际值；不能声称 EEE 现时一定关闭，更不能继续把“先随便关闭 EEE”当成未经核实的修复。

## 为什么当前终端不直接读取 BMCR/BMSR

原生 PHY 读函数 0x8001593c 已找到，见 `mdio-read-path-disassembly.txt`。它保存并暂时关闭中断，清 GPIO mode 的 MDIO 位，向 PCR0 发 read 命令，等待 PCR1 完成，再恢复引脚模式及中断状态。整个过程不是只读取 PCR0/PCR1 现值。

现有 CLI 的 reg 命令可以做裸硬件读写，但没有直接导出上述原生函数。把读事务拆成多条 CLI reg w/r 无法复制原函数的并发保护，并可能与驱动操作竞争；本轮不执行这种替代方式。尤其不能把 PCR0=0x33000004 误解为 PHY 0 的实时 BMCR。

另一个潜在稳健性问题是原生读/写函数等待完成位时未见有界超时，且处于关中断区。当前故障中 AP 管理常保持可达，不支持将其直接认定为本次故障的原因；这是单独的代码审查发现。

## 当前可支持的方向

现场已确认真实物理 link down/up、以及恢复 up 后仍可能不通。设备内部应继续聚焦 PHY 初始化/自动协商和掉线恢复，而不是再改无线功率、DHCP 或要求用户增加交换机。以上初始化差异为候选审查项，尚无证据支持把某个常量直接替换后刷机。

尚缺的是故障当时、经正确并发保护读取的 PHY 控制和状态。现有安全的只读终端查询还不能提供这项数据；若后续加入固件诊断，应先单独设计保护/超时/恢复行为、离线校验及恢复准备，不把未验证候选直接刷入设备。

复现离线比对：

```
python3 compare_phy_init.py /path/to/esw_rt3050.c
```

原网页固件候选未改动。20 MHz 试验已结束，AP 已恢复 20/40 MHz；后续以 CURRENT-DIAGNOSIS.md 的更新为准。
