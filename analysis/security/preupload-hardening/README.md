# 请求体处理前认证候选

2026-10-21用户明确授权后，本目录当前481ed957…制品已在其LV-UE01进行一次实验升级，管理恢复、新页面/读取认证和配置保留通过；见[实际升级记录](../../deployment/README.md)。文件保留实验标签；以下离线边界仍不等于全部硬件/业务已验证。

在 [第一阶段认证候选](../auth-hardening/README.md) 上另存第二阶段制品，不覆盖原网页或 PHY 诊断镜像。目的：在 POST 的 multipart 解析、上传暂存和流式 Flash 写入路径之前检查凭据。已验证受限原生分支和原 HTTP 解析/拒绝流程，尚未验证完整 HTTP 业务集成或实机效果。

## 实现与控制流

原 HTTP 路径检查既可进入 0x800103f0，也有分支进入 0x800103f4，因此将原 0x800103f8 的方法分支改为跳转守卫，保留其延迟槽。守卫放在第一阶段已取消调用的旧默认账户 helper 空间 0x8000e398..0x8000e424，代码 84 字节，剩余填零。原代码扫描只发现一处对该 helper 的直接 JAL，已在第一阶段取消；未发现对其地址的对齐字面量引用。这不是排除任意计算式间接调用的完整证明。

守卫读取原 HTTP 帧的方法字段：非 POST 转回原 0x8001075c 路径；POST 调用实际 auth_check，参数仍为原请求结构 sp+4。成功后恢复原请求体偏移 v1 并进入 0x80010400；失败调用原错误响应包装函数，以认证返回值为状态、Unauthorized 为信息，然后直接转向原清理入口 0x8000fe30，不进入请求体处理。

公开资源比较同时排除 POST：即使路径是 login.htm 或 js/app.js，也必须提交正确凭据。新登录表单通过 Cookie 加 GET 导航登录，未引入匿名 POST 登录接口。三个精确资源的普通 GET 保持可匿名访问；非空原始查询串必须认证，避免 GET 参数进入通用命令分发。

相对第一阶段 main 的许可范围为 0xdf98..0xe0e0、0xfff8..0xfffc（右端不含），共 264 个不同字节。所有其他字节一致；第一阶段的默认账户短路修补保持不变。没有使用清除的图片空间或移动代码、资源、分区。

## 验证结果及其范围

- [20 组认证回归](auth-results.json)通过：默认/非默认账户、正确/错误/缺失凭据、Cookie、公开资源和路径变体。
- [20 组守卫回归](preupload-results.json)通过：缺失/错误/正确凭据、公开与私有 POST 路径、原 0x800103f0/0x800103f4 两个入口、Cookie、非默认账户及 GET 路径。成功时核对请求体偏移恢复，各组核对栈恢复。
- 守卫回归执行实际 auth_check、字符串/Base64 函数及原 0x8000f838 错误响应包装函数。只拦截配置读取、时钟/日志和错误响应的头部/正文输出后端。失败时观察到 401 与 Unauthorized 参数，然后到达原清理入口；成功时停止于请求体入口。
- 第一阶段对照的 [失败记录](../auth-hardening/preupload-before-results.json)使用同一组最终 20 个用例，显示未加守卫时未授权 POST 可直接进入请求体。
- [30 组原 HTTP 解析实验](http-rejection-results.json)从 0x8000fc4c 执行原处理函数，输入合成 multipart 字节，覆盖私有/公开路径、缺失/错误/正确凭据、Authorization/Cookie 和单段/两段输入。18组无效请求均产生401、执行原清理函数、调用建模释放后端并从 HTTP 函数正常返回，栈恢复；12组有效凭据到达请求体处理边界后停止，未执行上传或 Flash。
- [独立制品校验](verification-results.json)通过：许可范围外全部字节、原 loader/头部非 CRC 字段、有限解压、FF 填充、CRC、SHA、跳转/调用目标及反汇编。见 [守卫与公开路径反汇编](guard-disassembly.txt)。

20组守卫实验停在请求体/清理入口。补充30组实验执行了原 HTTP 头部和路径解析以及拒绝后的清理控制流，但输入读取、缓冲区追加/分配、输出、释放和上下文释放后端仍使用模型。没有执行 multipart 解析、实际上传或 Flash，也未验证真实客户端收到401、资源释放器内部或真实连接关闭。有效凭据组停在请求体入口，不能称为已验证合法升级成功。这些结果不代表所有请求路径已覆盖或真机漏洞修复已确认。

## 制品

| 项目 | 结果 |
| --- | --- |
| 容器 / main 长度 | 718,108 / 2,174,360 字节 |
| 压缩 / 余量 | 655,364 / 53,400 字节 |
| uImage SHA256 | 481ed9575c53ff9ab6d5021638f225eb35cb6ac7b7839d4e0a65ec6a13ae4bb3 |
| 容器 | web-preupload.uimage.NOT-FOR-FLASHING.bin |
| main | main-preupload.NOT-FLASHABLE.bin |

WPS 默认关闭、新双语页面、无 jQuery/旧图片的修改继承网页基线。系统、无线驱动、网络栈、Bootloader 未升级；没有加入 HTTPS 或服务端 CSRF token。仍保留 NOT-FOR-FLASHING，不因尺寸合适或离线回归通过而认定可安全安装。

## 后续开发

继续验证认证成功后配置导入/上传能否保持原行为、更多续读路径、特殊方法与路径别名。不把已通过的拒绝流程模型扩大为全部业务或实际连接关闭已验证。X99 长期测试和串口工具不作为这些离线开发的前提。

复现：

```sh
python3 firmware-analysis/ap-192.168.1.2/security/build_preupload_candidate.py
python3 firmware-analysis/ap-192.168.1.2/security/test_native_auth.py --main firmware-analysis/ap-192.168.1.2/security/preupload-hardening/main-preupload.NOT-FLASHABLE.bin --report firmware-analysis/ap-192.168.1.2/security/preupload-hardening/auth-results.json
python3 firmware-analysis/ap-192.168.1.2/security/test_preupload_auth.py --main firmware-analysis/ap-192.168.1.2/security/preupload-hardening/main-preupload.NOT-FLASHABLE.bin --report firmware-analysis/ap-192.168.1.2/security/preupload-hardening/preupload-results.json
python3 firmware-analysis/ap-192.168.1.2/security/verify_preupload_candidate.py
python3 firmware-analysis/ap-192.168.1.2/security/emulate_http_rejection.py --main firmware-analysis/ap-192.168.1.2/security/preupload-hardening/main-preupload.NOT-FLASHABLE.bin --report firmware-analysis/ap-192.168.1.2/security/preupload-hardening/http-rejection-results.json
```

只访问本地文件；Unicorn 在本机需沙箱外初始化。原网页浏览器模拟测试不等同于本候选的真实 HTTP 后端验证。

## 后续兼容性与 GET 参数补充修复

见 [本轮复核](COMPATIBILITY-REVIEW.md)：16组GET、12组multipart、6组配置提取、6组上传暂存和3组原生loader均通过。公开资源的查询参数绕过已在当前候选修补；原参数表延迟解析，最终检查原始查询串。配置及writer后端仍未执行。以上尺寸与哈希已同步为本轮最终制品。
