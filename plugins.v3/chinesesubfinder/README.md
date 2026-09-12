# ChineseSubFinder

整理入库时通知 ChineseSubFinder 下载字幕（修复 API 失败、增加连接测试与诊断）。

## 功能

- 监听 MoviePilot 整理入库事件（TransferComplete），将入库的媒体信息推送给 ChineseSubFinder 触发字幕下载。
- 支持 API 失败自动重试与原因通知。
- 内置连接测试与诊断接口，便于排查与 CSF 服务的连通性问题。

## 配置

| 配置项 | 说明 |
|---|---|
| 启用插件 | 开关 |
| 发送通知 | 调用失败时将原因通过 MoviePilot 通知推送 |
| 服务器地址 | ChineseSubFinder 服务地址（含 http/https 前缀与端口） |
| API Key | ChineseSubFinder 的 API KEY |

## 使用说明

1. 部署并配置好 ChineseSubFinder 服务。
2. 在插件配置中填写服务器地址与 API Key，保存后插件会进行连接测试。
3. 整理入库后自动触发字幕下载；可在 MoviePilot 消息通知中查看失败原因。

## 版本

- 当前版本以插件类 `plugin_version` 与 `package*.json` 为准（V3 与 V2 同源维护）。
