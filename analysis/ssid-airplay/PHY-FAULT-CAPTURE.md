# 诊断固件故障现场采集

2026-10-22更新：当前为新版UI/安全+PHY组合版 `c2948bec9931d02837ccfe09b5f53aaf55b4e4cd00c1e6060c310f48a68b175a`。采集器优先选择组合版安装记录，只有不存在更新上传时才使用旧原版UI诊断记录，禁止在新上传未验证时退回旧基线。8项解析/记录选择测试通过；刷前正常采集035734Z、刷后真实link down完整采集040021Z均成功，见[部署记录](../deployment/README.md)。以下ae986324…为前一版历史基线。

当前已验证运行的诊断修正版 SHA256 为 `ae98632494f7df945e99ad534a905b009c388ed326991e50a2a8d2beab40481e`。基线见[刷写前后对照](../deployment/phy-baseline-comparison.json)，不是故障修复验收。

用户报告再次异常后，由代理在保留现场时执行一次：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 firmware-analysis/ap-192.168.1.2/ssid-airplay/capture_phy_fault.py
```

本机 Python 子进程联网需要沙箱外许可；沙箱拒绝不能解释成 AP 断连。没有自动轮询、自动重试、配置更改、重启或刷写。用户不需要手动运行脚本。若用户需要先恢复设备，可先恢复，但必须记录操作及顺序，不能将恢复后的读数当作原故障状态。

## 采集顺序

1. 查询固定白名单 POA、DMA 环索引与配置、中断状态；记录端口0 bit25。
2. 保存探测前 MAT，避免主动 HTTP 已刷新表项。
3. 只执行一次 `reg phy`，完整保留寄存器0/1/1/4/5/6，包含两次BMSR、重连计数和原始CP0 Count。
4. 单次 X99 HTTP 和认证 AP 状态 GET，保存运行时间。
5. 再取一组同样的硬件读数与 MAT，然后关闭连接。

命令与 HTTP 均有超时；全流程设45秒采集期限（包含登录时间，单次在途HTTP及关闭收尾可能略超过期限）。CLI中途失败即停止该次会话，不把后续回包错配给下一条命令；部分原始输出仍保存。PHY读取会向MDIO控制器发读事务，BMSR可能清除锁存位，不能称为完全被动观察；不写PHY配置。

## 输出与解释

每次创建独立 `phy-fault-captures/<UTC时间>/`：目录0700、原始回包和摘要0600。原始状态含网络信息，仅私有保存；摘要只保留MAT的MAC哈希，不输出账号密码。最新指针为 `latest-phy-fault.json`，不覆盖安装或首次基线记录。

`complete_capture=false` 表示记录不完整，不代表设备一定故障；`complete_valid=true` 仅证明PHY回包格式、范围、顺序和十六进制一致，不代表网络正常。两次BMSR不可合并或去重。重连基线2只覆盖已插桩的一条函数；需结合uptime、用户操作、回绕或重启判断，不能只见计数增加就认定掉线根因。DMA索引不变也可能是无流量；X99的HTTP失败还需结合真实有线接口选择与链路状态。

“AP中断触发X99放弃有线”仍是假设：需分别核对AP是否主动重连、PHY是否down、恢复up后DMA/MAT是否恢复，以及X99是否转为Wi-Fi，不能仅凭断电后恢复选择责任方。

## 本轮验证边界

7项离线解析测试通过：正常/全零、双BMSR、部分负错误、hex不一致、缺行/重复汇总、损坏/乱序、计数边界。另对安装时保存的真实回包离线回放，与已验收六项读数及基线计数2逐项一致。新组合采集流程尚未在下一次真实故障执行；本轮没有为此访问AP或再次清除BMSR锁存状态。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s firmware-analysis/ap-192.168.1.2/ssid-airplay -p 'test_phy_fault_capture.py' -v
```
