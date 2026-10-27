# 启动入口与 Flash 副作用核查

范围：仅本机备份的 U-Boot 代码和五组离线分支实验。没有操作 AP 按键、断电、重启、网络加载或刷写；实际按键接线、控制台入口、恢复及候选启动仍未验证。

## 启动时 GPIO 分支存在，但通向升级写入

`0xbc002238..0xbc002274` 设置 GPIO 模式后读取 `0xb0000624` 的 bit 6。离线执行原指令确认：该位为高时走 Normal Mode/menu；为低时进入 Upgrade Mode。仅凭代码不能确定 PCB 上哪个按键连接到该输入，不提供未测量的按键操作步骤。

Upgrade Mode 的可达后续路径包含：

| 调用点 | 操作 |
| --- | --- |
| 0xbc002300 | 调用 tftpboot 命令后端 0xbc00c020 |
| 0xbc002334 | 调用 Flash 写入后端 0xbc009488，目标偏移 0x50000，长度取下载大小 |
| 0xbc002378 | 调用擦除后端 0xbc008db8，偏移 0x30000，长度 0x10000 |
| 0xbc00244c/0xbc002ad0 | 转入 bootm 后端 |

代码对此擦除步骤的日志为 `Erase Factory block`。本机编译环境存储偏移常量（文件 0x16180）也是 0x30000；本报告不把它扩大解释为必然擦除无线校准区。后端实现和外层控制流已展开；离线实验替代了全部实际下载、Flash 写/擦和 bootm，仅验证成功返回模型中的调用顺序与参数，不验证错误处理和实机恢复。

**这条 GPIO 升级入口不适合当作不写 Flash 的 RAM 试启动入口。** 不能因为菜单中同时有 TFTP/RAM 字样就尝试开机长按按键。

## RAM 自动启动存在有条件的环境保存

菜单 1 的参数设置函数位于 0xbc001418，读取/编辑本机 IP、服务器 IP、文件名；与旧值不同时增加 0xbc017040 的标志/计数。菜单 1 随后设置 `autostart=yes`，调用 tftpboot。

TFTP 命令的自动启动分支 `0xbc00c398..0xbc00c41c`：

1. 读取 0xbc017040；若为零，直接进入后续 bootm。
2. 若非零，先修改环境中的 autostart、bootfile，然后在 0xbc00c3e4 调用 0xbc010300，再 bootm。
3. 0xbc010300 是 `saveenv` 命令（0xbc00d814）调用的同一后端。展开其实现可见读取一整块、更新 0x1000 字节环境、擦除 0x10000 字节块并写回的路径；编译偏移为 0x30000。

两组原分支实验分别将该标志设为 0/1，确认环境保存只在非零模型中调用。实验开始于 TFTP 已成功、autostart=yes 已选中的子分支，不能当作完整 TFTP 或完整环境编辑流程仿真。

因此，**选择 RAM 加载并不保证整个流程不写 Flash**。环境保存是已定位的具体副作用，不能再只说“尚不清楚是否保存环境”。手动控制加载与启动、避免自动保存的其他控制台流程仍需独立验证，当前也没有已验证的无串口入口。

## 证据与复现

### 下载失败不会阻止升级入口继续调用擦写

新增四组离线实验执行原始 `tftpboot` 命令和 Upgrade Mode 调用者，只有网络循环与 I/O 后端使用替身。将 NetLoop (`0xbc005048`) 的返回值建模为 -1 后，原命令通过 `0xbc00c18c` 的负值分支返回 1；调用者在 `0xbc002308` 收到该失败值后，没有检查它，仍调用 `0xbc009488` 固件写入后端，随后调用 `0xbc008db8` 擦除偏移 `0x30000`、长度 `0x10000`。

下载长度全局变量分别建模为 0 和 718108，写入后端分别返回 0 和 -1，四种组合都到达上述擦除调用，再到 bootm 拦截点。非零长度是假设的残留值，并非实机观测；本实验不执行写入/擦除后端，因此长度为零时后端实际会做什么并未验证。

这确认了**调用者缺少失败检查**，不证明缺失服务器、文件或每一种超时都会返回 -1；网络循环也可能重试而不返回。因此不能把“不启动 TFTP 服务器”或“不提供文件”视作安全的升级入口探测方法。这与运行时 X99 掉线是不同问题，不作为掉线根因。

证据：[boot-failure-experiment.json](boot-failure-experiment.json)。复现：`python3 firmware-analysis/ap-192.168.1.2/recovery/emulate_boot_failure.py`。只访问本地备份，全部网络和 Flash 后端均被拦截，没有访问 AP、发包、重启或生成镜像。

五组实验（GPIO 高/低两组、升级后半段一组、RAM 自动启动标志两组）通过，见 boot-path-experiment.json。使用的启动区 SHA256 为 `5830037ccd300009cc51f05e275d450a9d35ce7d6e3a24aecab96ff7e1f7c2c8`，覆盖前 0x30000 字节，与新双份备份同区一致。

- `boot-selection-full-disassembly.txt`：菜单、GPIO 选择及控制流，附 GOT 解析。
- `button-upgrade-callees-disassembly.txt`：写入/擦除及初始化调用。
- `ram-tftp-handler-disassembly.txt`：TFTP 自动启动和环境保存条件。
- `environment-save-disassembly.txt`：保存环境的读块/擦除/写回实现。
- `boot-transfers-disassembly.txt`：命令表关联与 reset 等后端。

复现：`python3 firmware-analysis/ap-192.168.1.2/recovery/emulate_boot_paths.py`。只读本地备份，输出分析 JSON；依赖本机现有 Unicorn，当前 macOS 需在沙箱外初始化。脚本不访问网络，不生成固件镜像。
