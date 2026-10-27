# 后端认证第一阶段候选

在现有新版网页候选上完成独立离线补丁，未刷入 AP。它不是 PHY 诊断镜像，也没有更新系统、网络栈或无线驱动。X99 长期观察不作为本阶段前提。

## 实现

- 取消 auth_check 中的默认账户短路：0x8000e560 的 helper 调用改为将 v0 置 1，使后续进入正常凭据校验。保留原账户、密码、Cookie/Basic 解析和会话逻辑；默认 admin/admin 仍是一组有效凭据，但必须提交，不能匿名访问。
- 用精确路径比较替代公开资源子串搜索。仅允许 login.htm、js/app.js、favicon.ico；兼容规范化名称和单个前导斜杠，不接受后缀、路径中包含 login 或双斜杠的变体。字符串直接引用新版资源名，不新增数据分配。
- 新登录页依赖 app.js；原子串规则只含 jquery，没有覆盖此脚本。取消免认证时必须同时保障脚本可加载。

额外修改 main 文件中的两个范围（右端不含）：0xe024..0xe0e0、0xe160..0xe164，共 164 个不同字节；其余内容逐字节等于已有新版网页 main。精确比较函数代码 156 字节，位于原 188 字节函数空间，剩余填零。不移动后续地址，不占用旧图片区域或新增执行区。

## 验证

同一组 20 个合成请求直接执行实际 auth_check、公开路径比较、原字符串函数和原 Base64 解码。配置读取、账户表、时钟及日志使用模型；没有发送 HTTP、操作真实配置或 Flash。

未修补网页基线的 [对照结果](../auth-before-results.json) 复现匿名/错误凭据放行和非默认账户无法加载新脚本。补丁的 [20 组结果](auth-after-results.json) 全部通过，包括默认/非默认账户、缺失/正确/错误凭据、Cookie、公开资源及名称变体，均正常返回并恢复栈。

原生 HTTP 解析器有不带前导斜杠的路径形式；补查时发现首版精确比较遗漏这一形式，修正后重跑全部 20 组。未把最初只覆盖带斜杠形式的 12 组结果当作最终结论。

独立验证器不导入构建器：固定网页基线 SHA，检查全部非目标字节、调用/分支及三个资源地址、反汇编、尾部填充、解压上限、两项 CRC、未改 loader/头部字段和清单一致性。见 [验证结果](verification-results.json) 与 [反汇编](public-gate-disassembly.txt)。

| 制品 | 结果 |
| --- | --- |
| uImage | 718,108 字节 |
| 解压 main | 2,174,360 字节 |
| 压缩 / 余量 | 655,398 / 53,366 字节 |
| uImage SHA256 | a8d20ebf90669c86fb79ce85abf662b856f2d07a1c4fb40d5c0eb208f91951b0 |

原网页候选 SHA75581dd659ed625e7547ce91b89803f0983df49b7a537c0ebb7e1302bdf1178f 保持不变；本目录分别保存 main-auth.NOT-FLASHABLE.bin 和 web-auth.uimage.NOT-FOR-FLASHING.bin。

## 尚未完成

**本阶段不解决流式上传早于认证的问题，也不证明配置写入或完整 HTTP 分发已安全。** 页面 CRC/文件名限制仍不是后端保护。下一阶段需将认证置于上传处理和 Flash 副作用之前，并验证失败路径不进入上传/擦写后端；不进行实机上传试探。

继续追踪发现，HTTP 路径检查的部分分支可进入 0x800103f4，单独在 0x800103f0 加检查不保证覆盖；0x80010988 又会进入 0x80010438 的续读路径。补丁需考虑这些控制流，不能只在一个看起来靠前的位置插入调用。失败时如何复用原响应、会话状态和清理路径也必须验证。本候选暂未改动这些位置。

公开路径只允许上述三项是新版页面的范围选择，旧页面、语言脚本和工厂测试入口不再匿名开放。未验证所有原路由别名、HTTP 传输、实际浏览器与新后端联动、真机启动、缓存或恢复。没有提供 HTTPS，Basic/Cookie 仍经 HTTP 传输；本阶段不能称为完成所有安全加固。候选保留 NOT-FOR-FLASHING。

## 复现

```sh
python3 firmware-analysis/ap-192.168.1.2/security/build_auth_candidate.py
python3 firmware-analysis/ap-192.168.1.2/security/test_native_auth.py --main firmware-analysis/ap-192.168.1.2/security/auth-hardening/main-auth.NOT-FLASHABLE.bin --report firmware-analysis/ap-192.168.1.2/security/auth-hardening/auth-after-results.json
python3 firmware-analysis/ap-192.168.1.2/security/verify_auth_candidate.py
```

均只访问本地文件；本机 Unicorn 初始化需沙箱外运行。浏览器的原 74 项模拟流程没有覆盖本补丁，不能用它们代替原生后端验证。

后续GET路由审查发现，公开资源带CMD查询参数也可能进入通用命令分发。此第一阶段版本不处理该问题，第二阶段的最终修补及证据见[兼容性复核](../preupload-hardening/COMPATIBILITY-REVIEW.md)。
