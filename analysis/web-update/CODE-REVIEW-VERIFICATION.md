# 五项代码审查修复复核

本轮核对用户提供的已修复项，没有进一步修改产品代码。重新构建复现现有候选，verify.py 全部通过。

| 审查项 | 核对结果 |
| --- | --- |
| Open/WEP 的 WPA 加密下拉框 | securityFields 对 AES/TKIP/TKIPAES 以外值使用 AES；非 WPA 时仍隐藏加密项，不改变实际 Open/WEP 安全类型。已保存 Open/WEP 的本机和上游配置分别切换三种 WPA 模式，均无需手动选择加密即可保存。扫描选择 Open/WEP 后切换 WPA 也通过。 |
| 尺寸、余量和摘要一致性 | 实际 LZMA 流 655421 字节，尾部 0xFF 为 53343 字节；build-manifest.json、size-capacity-evidence.json、README、SIZE-CAPACITY-REVIEW、TEST-READINESS、WIRELESS-FEATURE-REVIEW 均一致。 |
| 本机 WPA 密钥同步 | 本机设置新 WPA 密钥时同步已有 WLN_WscNewKey；上游密码单独变化不修改它，缺少可选字段时不凭空添加；WLN_WscConfMode 仍为 0。 |
| 空 SSID 默认值 | render 对初始空名保留自动命名意图，stats 调用 naming；取得设备 MAC 后正常生成默认名。用户手动清空后再刷新状态不会被默认名覆盖，无自动写入。 |
| 删除无用代码 | build.py 不再含 replace_line；settings.js 不再含不可达的 window.url/setok 页面检查。完整旧流程回归未发现退化。 |

验证：原七套 localhost 流程共 74 条结果通过，新增 review-regression-test.cjs 四组结果通过（合计 78）；覆盖桌面/手机和中英文。测试仅访问 127.0.0.1 模拟服务，没有改动 AP。

测试脚本与结果：/private/tmp/keyauto-ap-web-tools/review-regression-test.cjs、review-regression-results.json，以及 run-all.cjs 的七套结果。

候选 SHA256：75581dd659ed625e7547ce91b89803f0983df49b7a537c0ebb7e1302bdf1178f

容器仍为 718108 字节，解压主程序仍为 2174360 字节。上述验证不包含真机启动、射频效果、刷写接受或恢复测试；物理 Flash 容量仍待芯片 ID 等设备证据确认。
