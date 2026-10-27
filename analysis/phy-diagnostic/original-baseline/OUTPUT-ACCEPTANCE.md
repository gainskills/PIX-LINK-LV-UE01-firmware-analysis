# 诊断输出离线验收

使用 [probe_output_acceptance.py](../../../logic/phy-diagnostic/probe_output_acceptance.py) 执行已写入候选 main 的 CLI 回调与诊断负载，结果保存于 [diagnostic-output-acceptance.json](diagnostic-output-acceptance.json)。八组实验通过；候选镜像未修改，没有访问设备。本实验不增加生产解析器或现场查询工具。

| 模型情形 | 已验证输出 |
| --- | --- |
| 第一次 BMSR 低、第二次高 | 两行分别保留 7809 和 782d |
| 两次 BMSR 均低 | 两行均保留 7809，不去重 |
| 六个寄存器均为零 | 六个有效原始结果，不当成缺失 |
| 初始控制器忙 | result=-2、hex=fffffffe，停止读取 |
| MDIO 超时 | result=-3、hex=fffffffd，停止读取 |
| 计数到达上限 | 4294967294 经一次入口变为 4294967295 |
| 计数回绕 | 4294967295 经一次入口变为 0 |
| 第二次 BMSR 前控制器忙 | 保留前两次成功结果和第三行错误，不继续读取 |

每组均检查 CP0 Status、引脚复用及栈指针恢复；发出的 MDIO 命令均为读取，没有 PHY 配置写入。计数实验只执行插桩入口，不执行原重连函数主体。

## 后续现场记录规则

完整记录应有一条汇总及按顺序读取的六行：寄存器 0、1、1、4、5、6。两次 BMSR 必须保留读取顺序，第一次查询可能清除锁存状态；不能按寄存器号覆盖或去重。六行成功仅表示完整原始采样，不代表网络连通正常。

每行同时保留有符号 result 与 hex，核对它们的 32 位表示。%04x 是最小宽度，负数会输出八位十六进制；不得截断成 16 位后当作 PHY 值。成功值可以为零。错误、缺行或传输截断不得补零，不能形成完整链路状态结论。

例如第二次 BMSR 前出现忙条件时，实际候选格式与参数渲染为：

```text
PHYDIAG relink_calls=0 last_cp0_count=2271560481
PHYDIAG p0 reg=0 result=13056 hex=3300
PHYDIAG p0 reg=1 result=30729 hex=7809
PHYDIAG p0 reg=1 result=-2 hex=fffffffe
```

这里只发出两次 MDIO 读取；第三行表示读取被忙检查拒绝。保留这个部分结果，不把它归为完整采样，也不推断物理链路已断。

relink_calls 是单一已定位函数的 32 位入口计数；减少或归零可能是回绕或启动重置，需结合 uptime 与操作记录。last_cp0_count 是未经频率校准的原始 32 位计数，不换算为秒。

## 实验边界与复现

MMIO、CP0 Count 和 printf 使用已有 Machine 模型。文本由真实候选的格式串及参数渲染，并非真实串口或 Telnet 输出。中途忙条件是合成注入，不是设备故障证据；没有执行 Telnet、CLI 分词器、原重连主体或真实 PHY。当前 AP 原固件不支持 reg phy。

```sh
python3 firmware-analysis/ap-192.168.1.2/phy-diagnostic/probe_output_acceptance.py
```

本机 Unicorn 初始化需要在沙箱外运行。八组输出实验与既有 21 项诊断测试分别记录，不能当作实机启动、恢复或根因修复验证。候选继续标记 NOT-FOR-FLASHING。
