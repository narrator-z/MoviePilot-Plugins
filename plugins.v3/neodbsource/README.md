# NeoDBSource（NeoDB源）

让探索、推荐和媒体识别支持 NeoDB 数据源（电影/剧集/动画）。

## 功能

- 通过 `get_module()` 注册 NeoDB 媒体识别模块，只处理本源请求。
- 支持探索（Discover）与推荐页面的 NeoDB 数据源接入。
- 从 NeoDB 条目的 `external_resources` 提取 tmdb/douban/imdb 关联 ID 写入 `MediaInfo`，保证订阅等链路可用。
- 提供 NeoDB API 地址与可选令牌配置。

## 配置

| 配置项 | 说明 |
|---|---|
| 启用插件 | 开关 |
| API 地址 | NeoDB 实例地址（默认官方实例） |
| 访问令牌 | 私有实例或受限接口使用的 Bearer Token |

## 使用说明

1. 启用插件并确认 API 地址可访问（公开实例无需令牌）。
2. 在探索/推荐页面选择 NeoDB 来源浏览；识别 NeoDB 链接或条目时自动走本插件。
3. 涉及订阅时，插件会自动补全跨源关联 ID。

## 版本

- 当前版本以插件类 `plugin_version` 与 `package*.json` 为准（V3 与 V2 同源维护）。

## 致谢

- 基于原作者 [wumode](https://github.com/wumode) 的 NeoDBSource 适配维护。
