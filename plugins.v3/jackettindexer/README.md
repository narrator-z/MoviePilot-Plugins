# JackettIndexer（Jackett索引器）

集成Jackett索引器搜索，支持Torznab协议多站点搜索。仅索引私有和半公开站点。

## 功能

- 将 Jackett 中配置的索引器注册为 MoviePilot 可用的站点资源来源。
- 通过 Torznab 协议多站点并发搜索，支持缓存与去重。
- 提供 Agent 工具（搜索种子、列出索引器），可在 MoviePilot 智能体中使用。
- 支持定时同步索引器列表（默认每 12 小时）。

## 配置

| 配置项 | 说明 |
|---|---|
| 启用插件 | 开关（开启后使用 Jackett 进行搜索） |
| Jackett 地址 / API Key | Jackett 服务连接信息 |
| 代理 | 是否经代理访问 |
| 定时周期 | 索引器同步 Cron |

## 使用说明

1. 在配置页填写 Jackett 地址与 API Key 并保存。
2. 插件会拉取 Jackett 索引器列表并注册；仅处理私有（private）与半公开（semi-private）索引器。
3. 搜索时自动聚合 Torznab 结果；可通过智能体工具 `搜索种子` / `列出索引器` 调用。

## 版本

- 当前版本以插件类 `plugin_version` 与 `package*.json` 为准（V3 与 V2 同源维护）。
