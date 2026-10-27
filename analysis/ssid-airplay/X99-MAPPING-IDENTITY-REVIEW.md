# X99 有线身份与 AP 映射已交叉核对

## 新的实机证据

UTC 2026-10-21 05:58:40 左右，先登录 AP 只读查询 MAT，再访问 X99 自带设备信息查询接口。结果：

| 核对项 | 结果 |
| --- | --- |
| X99 自报型号 | SRS-X99 |
| 当前连接类型 | wired |
| IPv4 地址 | 192.168.1.4 |
| X99 DHCP client | off，即手动地址 |
| 查询前 AP 已有 X99 表项 | 是 |
| 表项 MAC 与 X99 有线 MAC 相符 | 是 |

见 [脱敏结果](mat-captures/20261021T055840Z-x99-identity.json)。完整 MAC 没有输出或保存；双方在内存中按相同方式计算 SHA256 指纹后比较。此前 `20261021T054938Z-dma.json` 的六份探测前/后指纹也与这次设备自报有线 MAC 指纹一致。

这比仅看到 IP 表项多验证了映射对象，但仍是正常可达窗口，不能排除故障时条目丢失、被覆盖或其他转发异常。也不将无线中继在上游显示 AP MAC 的正常转换误认为 X99 有线 MAC 应当变化。

## 查询来自设备自身页面

读取了 X99 的 `settings/devicedetails.html`、`settings/devicedetails.js` 和 `settings/xmlhttprequestsupport.js`。页面明确将 `network.macaddress_wired` 显示为 Wired MAC，并用 `type: http_get` 请求 `/cgi-bin/request.fcgi`；`http_set` 为不同操作。

本轮只发送固定五个查询字段：`system.modelname`、`network.connectiontype`、`network.macaddress_wired`、`inet4.dhcp`、`inet4.ipaddress`。HTTP 方法为 POST，但载荷语义是页面已有的只读 http_get，没有调用 http_set、Apply、重启或工厂复位。没有读取 Wi-Fi 密码或保存原始接口响应。

[verify_x99_mapping.py](../../logic/ssid-airplay/verify_x99_mapping.py) 拒收错误响应类型、重复/缺失字段、非法 MAC、全零或 multicast MAC；两个等价 MAC 格式及六种无效响应场景的本地检查通过。脚本在目标查询前读取 AP 表项，避免先访问 X99 对要观测的 MAT 状态造成刷新。

## 故障采集可使用已验证身份

已保存 [身份参考](mat-captures/x99-wired-identity-reference.json)，包含型号、IP、有线 MAC 指纹、核对时间、源记录路径和 SHA256，没有完整 MAC。

`capture_dma_state.py` 在采集前校验该参考与源结果一致，再为每次 MAT 摘要给出 `x99_mac_matches_verified_reference`：

- `true`：已打印的目标记录都匹配该有线身份。
- `false`：已打印的目标记录至少一个指纹不匹配。
- `null`：没有可用的目标记录/参考，不能判断；不等同于映射错误或表为空。

这样故障时不必先查询 X99 本身来取得 MAC。最新采集自测为六项寄存器解析、六项 MAT 摘要及三项参考匹配检查，均通过；身份参考的实机来源已经验证，新增比较字段在本地合成数据上验证，没有为了比较字段再次重复采正常基线。

本轮没有 AP 配置改变、日志级别变更、寄存器写、清表、MDIO 事务、设备重启或刷写。AP 连接和所有短时采集进程已关闭。
