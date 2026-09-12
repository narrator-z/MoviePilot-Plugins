# ProwlarrExtend

扩展检索以支持Prowlarr站点资源。

## 功能

- 在 MoviePilot 站点资源检索链路中聚合 Prowlarr 的索引器搜索结果。
- 读取 MoviePilot 站点配置中的 Prowlarr 绑定信息，按索引器并发搜索。
- 支持定时同步（APScheduler），并对结果做去重与规范处理。

## 配置

| 配置项 | 说明 |
|---|---|
| 启用插件 | 开关 |
| 其他选项 | 详见插件配置页（Vuetify 表单） |

## 使用说明

1. 确保已在 MoviePilot 中配置 Prowlarr 相关站点。
2. 启用插件后，搜索时会自动聚合 Prowlarr 资源。

## 版本

- 当前版本以插件类 `plugin_version` 与 `package*.json` 为准（V3 与 V2 同源维护）。
