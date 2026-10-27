# 原生兼容性与 GET 参数修复

本轮没有访问 AP。对照为已有新版网页 main，SHA256 3385f574b110096a4446cf6beef365c95c63e41ac5be80d1cca5b5d8842d81b8；当前安全候选容器 SHA256 481ed9575c53ff9ab6d5021638f225eb35cb6ac7b7839d4e0a65ec6a13ae4bb3。原网页制品没有覆盖。

## 新发现及修复

通用处理器可在 GET 公开资源后继续分发查询串里的 CMD。之前第二阶段容器 893f6cdb38bf5bbedc71f5aa4359d57a2ccf9604d6a9ceebb2e1183768e473f0 允许匿名访问 login.htm / js/app.js 携带 CMD 到达命令分发器，见 [失败对照](login-query-before-results.json)。实验在分发器入口停止，没有执行实际命令。

参数表按需解析，认证时可能仍为空，因此最终补丁检查原始查询串。公开例外要求三个精确资源、非 POST、查询串缺失或为空。非空查询串均要求认证，包括 v=1 等缓存参数；新登录页脚本 URL 不带查询串。正确凭据仍允许查询请求。代码使用原188字节函数全部空间，没有新增执行区或移动地址。

## 本轮验证

| 实验 | 数量 | 执行与停止边界 |
| --- | ---: | --- |
| [GET 路由](login-get-results.json) | 16 | 原 HTTP 解析/认证/路由/静态回调；输出建模，受保护导出或命令在入口停止 |
| [multipart 分发对照](authenticated-post-results.json) | 12 | 原版/候选原生解析出的 CMD/CCMD/GO 相同，停在命令或暂存入口 |
| [配置文件提取](config-import-results.json) | 6 | SYS_CONF、CCMD=3 到原生文件提取；长度/哈希等于合成 profile，在导入器0x800089c0首条指令前停止 |
| [上传文件暂存](upload-staging-results.json) | 6 | 原生文件定位、长度提取和暂存复制；16字节非镜像夹具一致，在 writer0x80006614首条指令前停止 |
| [原生 loader](native-loader-results.json) | 3 | 原版/候选的原 MIPS 解压器到达 main入口并逐字节一致；坏属性进入失败分支，不执行main |

全部通过。POST 对照覆盖 Authorization、Cookie，以及完整输入、请求头分段、请求体中途分段。配置到导入器前，原版认证2次、候选3次；上传到 writer 前，原版0次、候选1次。增加了前置检查，所测原业务参数和文件字节未变。

GET 覆盖匿名登录页/脚本、根路径/主页、正确/错误 Cookie、导出保护、公开 URL 的 CMD 参数、空查询和缓存参数。静态正文哈希匹配嵌入资源。原路径先有一次零长度写入，实验保留该事件；它不贡献正文，不作为固件缺陷。

此前20组认证、20组守卫、30组 HTTP 拒绝模型已在最终候选重跑通过，独立制品校验也通过。各组分别记录，不混称硬件测试。

## 制品与边界

容器718,108字节，main2,174,360字节；压缩655,364、余量53,400字节。相对第一阶段 main 的许可范围仍是0xdf98..0xe0e0、0xfff8..0xfffc，共264个不同字节。

配置导入器、配置应用/持久化、上传 writer、镜像接受和擦写均未执行。分配、输入、输出、释放后端仍使用模型；没有验证实际浏览器/网络、全部方法/URL编码/别名、真实会话超时、射频或恢复。原生解压成功不代表完整启动通过。没有新增 HTTPS 或 CSRF token。

初次暂存断言曾把16字节夹具手算为15，已改为从字节串计算；未为此修改固件。

脚本：[GET](../../../logic/security/emulate_login_get.py)、[multipart](../../../logic/security/emulate_authenticated_post.py)、[配置提取](../../../logic/security/emulate_config_import.py)、[上传暂存](../../../logic/security/emulate_upload_staging.py)、[loader](../../../logic/security/emulate_candidate_loader.py)。均只访问本地文件；本机 Unicorn 初始化需沙箱外运行。
