# 逻辑代码 / Logic

保持原有模块名称，以便追溯已有实验。使用根目录tools/prepare_workspace.py将代码、分析输入和固件按workspace-map.json组合到Git忽略的.work目录，然后从.work运行既有脚本；不要将原始main文件当作可刷入uImage。

- web-update：新管理页面、配置逻辑、打包和离线浏览器检查。
- security：HTTP认证补丁、离线验证和历史设备操作工具。
- phy-diagnostic：MIPS诊断负载、构建、镜像验证和回归测试。
- recovery：备份/恢复路径调查与离线检查。私有备份校验需要本地捕获数据。
- ssid-airplay：以太网/上游状态分析、故障采集和有限模型。

历史实机安装、回退、扫描和采集脚本并非适用于任意设备的一键工具；离线测试不会调用它们。默认安装依赖不会连接AP。
