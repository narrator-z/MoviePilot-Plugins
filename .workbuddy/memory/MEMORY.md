# MoviePilot-Plugins 项目长期记忆

## 一、插件开发硬性规则（踩坑固化）

1. **版本号双字段必须同步**：`__init__.py` 的 `plugin_version`（MP 加载/显示/日志用）与 `package*.json` 的 `version`（Market 更新比较用）必须一起改。只改其一 → Market 显示版本不变且反复提示更新。
2. **清单条目必须有同名代码目录**：`package.v2.json` 对应 `plugins.v2/<id>/`，`package.v3.json` 对应 `plugins.v3/<id>/`（目录全小写，`pid.lower()` 匹配）。**v3-only 插件只进 v3 清单和基础索引，不进 v2 清单**（登记了会指向空目录导致安装失败）。
3. **改元数据前先 grep `plugin_author` 是否被业务逻辑引用**：JackettIndexer 用它当域名占位符（见坑位 7）。
4. **本地 `py_compile` 查不出运行期未定义名称**（漏 import 枚举 / NameError），只在容器实际加载时暴露。改完应在容器内验证：`docker exec moviepilot python3 -c "from app.schemas.types import ..."`。
5. **排查"插件不显示/安装失败/不生效"**：SSH 上 NAS 查 `/config/logs/moviepilot.log` 的 `加载插件 X 失败`，不要猜网络/镜像。Market 安装失败时 MP 把插件备份到 `/config/plugins_backup` 但不装回 `/config/plugins` → 表现为不显示。
6. **容器镜像可能与本地源码不一致**（用户自建 fork 镜像），导入路径、事件枚举以容器内为准，别只信本地 `E:\github\MoviePilot`。

## 二、仓库清单维护（2026-09-12 修订）

- 三份索引：`package.json`（基础，无 VERSION_FLAG 实例读）、`package.v2.json`、`package.v3.json`。
- **基础索引必须显式带 `"v3": true`** —— `is_plugin_info_compatible` 在 flag=v3 时要求条目声明，否则读到也被过滤；配合 `system_version: ">=3.0.0"` 阻止低版本误装。
- v2 清单格式差异：icon 用相对文件名（`"Jackett_A.png"`），**无** `release` / `system_version` 字段。
- 现状：v3 清单 7 个（LunaTVSource 归 OneBigMoon，其余 6 个 narrator-z）；v2 清单 6 个（无 LunaTVSource，v2 无代码）。
- **发版校验脚本**（必做）：比对 清单 version/author ↔ 代码 `plugin_version`/`plugin_author` ↔ 目录集合 ↔ JACKETT_DOMAIN 占位符。正则必须用 `^\s*字段名\s*=`（类变量有缩进，否则全匹配为 None 误报不同步）。

## 三、LunaTVSource 上游同步（fork 维护，2026-09-12 建立）

本仓库是**手工建的**（非 GitHub fork，无共同历史），不能用 `git merge` 同步上游 jxxghp/MoviePilot-Plugins。

- **基线定位**：NAS 上 `git clone --unshallow` 上游 → 遍历 `git log --format=%H -- plugins.v3/lunatvsource/__init__.py` 各提交 → difflib 与本地比对取差异最小者。当前基线 **上游 0.4.59（03b0fd2）**。
- **⚠️ 比较必须用 difflib 的 `splitlines()` 结果，不能用 `diff` 命令**：`core.autocrlf=true` 让工作区 CRLF、git 内 LF，`diff` 会把整个文件判为不同（`1,5672c1,5672`），完全看不出真实差异。
- **本分支定制仅 2 处（都在 `cms.py`）**，其余 py 文件与上游基线逐行一致：
  1. `_BRACKET_TAG_RE` + `_normalize_cms_title()`：苹果 CMS 片名 【...】/[...] → `(...)`，规避核心 `is_anime()` 把「剧名【年份】【地区/类型】【字幕】」误判为动漫。
  2. `_result_from_item()` 里 `title = _normalize_cms_title(_text(...))`。
- **同步策略**：版本差距大时不要 cherry-pick，直接**上游全量替换 + 重新应用这 2 处定制**，并把上游 changelog 并入清单 history。
- 上游是多文件 + 前端 dist 插件（ai/cms/downloader/m3u8_engine/naming/classification + dist + vendor/N_m3u8DL-RE），替换要整目录覆盖，别只换 `__init__.py`。
- 部署后**用 `__pycache__` 里有无 pyc 判断插件是否真被加载**（比翻日志可靠）：已加载的插件目录下会有 `.pyc`，未启用的为 0 个。

## 四、插件市场机制（v3.0.37 实测，2026-09-12）

- `settings.VERSION_FLAG='v3'`，`get_compatible_version_flags()=['v3','v2']`；`PLUGIN_MARKET` 默认 74 个仓库，本仓库排在最后一位。
- 索引选择：有 flag 读 `package.{flag}.json`，无 flag 读 `package.json`。基础索引现已补齐（此前为空 `{}`，会让无 flag 实例解析出 0 个插件）。
- **跨仓库去重（`catalog.py:370-386`）**：按插件 ID 去重，**版本号高者胜出**。LunaTVSource 已由 0.4.60 抬至 0.4.83 压过 jxxghp 的 0.4.82。
- **市场页（`state=market`）排除已安装且无更新的插件**（`catalog.py:509-520`）——「按作者搜索只剩几个」的真正原因，不是分页也不是 bug。看已装的去「已安装」页（`state=installed`）。
- **可见数量 = 本仓库条目 − 已装且无更新的条目**。2026-09-12 实测：用户已装 ChineseSubFinder/JackettExtend/StuckDownloadGuard/NeoDBSource（版本与市场一致）→ 6 个 narrator-z 插件里只显示未装的 ProwlarrExtend、JackettIndexer 共 2 个。判断"看不全"前先算这个。
- 判定「已安装」看 `systemconfig.UserInstalledPlugins`（不只是 `/config/plugins/` 目录，fork 镜像内置 `/app/app/plugins/<id>/` 也算）。
- ⚠️ **旧结论「API 默认只返回 50 条」已作废**：`plugin.py:207` 现为 `max_results=None`（不传即全量）；仅传了 `page`/`count` 才分页（默认 50）。前端市场页实测不带分页参数。

## 五、NAS / 部署环境

- SSH：`192.168.31.145:22022`，用户 `narratorz`，密钥 `~/.ssh/id_ed25519_1panel`。
- 容器：**`moviepilot`**；插件目录 `/config/plugins/<id>/`，备份 `/config/plugins_backup/`，日志 `/config/logs/moviepilot.log`。代码 `/app/app`，**前端静态 `/public/assets/`**。
- 部署：本地 scp → `docker cp` 进容器 → `docker restart moviepilot`；冷启动 30–60s 后查日志。
- 调试：`docker exec moviepilot python3` 可直接 import 验证；`PluginManager()` 直接 import 是未初始化实例，无法验证运行时源生成。
- 容器内跑脚本：`docker exec -i moviepilot python3 - < script.py`。**应用工厂是 `/app/app/factory.py`**（`app.main` 的 app 只有 6 条路由，不能用于 TestClient）；版本取 `app.runtime.version.get_app_version()`。
- ⚠️ **本机工具环境出不了外网**（TLS/SSH 握手全超时）。**git push 改为经 NAS 中继**（NAS 能出网且 SSH key 已授权 GitHub `narrator-z`）：
  `git bundle create <file> --all` → `scp -P 22022` 到 NAS `/tmp` → NAS 上 `git clone` + `git fetch <bundle> main` + `git merge --ff-only FETCH_HEAD` + `git push origin main` → 清理 `/tmp`，本机 `git update-ref refs/remotes/origin/main <sha>`。完整命令见 2026-09-12 日志。

## 六、关键坑位

1. **fork 镜像内置插件 shadow Market 副本**：`/app/app/plugins/neodbsource/` 与 Market 装的 `/config/plugins/neodbsource/` 同名，实际加载的是 `/app/app` 内置那份。修代码必须 docker cp 到内置路径（chinesesubfinder、stuckdownloadguard 只有内置路径，无 `/config/plugins` 副本），清 `__pycache__` 后重启。
2. **`MediaInfo.year` 是 str 不是 int**：详情端点有 response_model 校验，`int(...)` 触发 `ResponseValidationError` → HTTP 500。一律 `str(year)`。
3. **`MediaType` 枚举值是中文**：`MediaType.MOVIE.value == "电影"`，要传中文，传 `MOVIE` 会 ValueError（假 500）。
4. **图片代理已正确配置**：`IMAGE_PROXY_ALLOWED_PRIVATE_RANGES=["198.123.0.0/16","fdfe:dcba:9876::/64"]` 覆盖 clash fake-ip。测试硬传 `None` 会误报 non_global_dns_result。容器 `settings.PROXY=None`，fake-ip IPv6 失败后回退 IPv4 可达，无需处理。
5. **列表缩略图优先取 `poster_path`**：只设 `cover` 会显示空白。
6. **post_message 签名已变（影响所有插件）**：fork 为 `post_message(channel=None, mtype=None, title=None, text=None, image=None, link=None, userid=None, username=None, **kwargs)`。**禁止** `self.post_message(Notification(...))`（整个对象被当 channel 传入 → channel 校验崩溃 → 所有通知失效）。正确：`self.post_message(mtype=NotificationType.Plugin, title=..., text=..., source=self.plugin_name)`。
7. **JackettIndexer 的 `plugin_author` 是业务变量**：`JACKETT_DOMAIN = "jackett_indexer.<author小写>"`，运行时 `replace(plugin_author.lower(), indexer_name)` 生成域名。**占位符必须与 `plugin_author.lower()` 完全一致**，否则 replace 不命中 → 所有索引器共用同一 domain → 功能失效。v2/v3 两份代码已同步为 `narrator-z` 并加警示注释。

## 七、探索页自定义数据源（NeoDBSource）关键机制

- 点击条目 → `media.py:media_info` → `parse_media_key("neodb:tv.uuid")` → `async_recognize_media(source="neodb", ...)`。
- **必须把 recognize 方法经 `get_module()` 注册为插件模块**（`_enabled` 即返回 `recognize_media`/`async_recognize_media`），不能依赖「媒体识别」子开关或 ChainBase 补丁。
- 注册方法要**只处理本源**，其余返回 None 交还核心，否则抢在 TMDB/豆瓣前「赢者通吃」。
- NeoDB 条目 `external_resources[]` 含 tmdb/douban/imdb 映射，正则提取写入 `MediaInfo.tmdb_id/douban_id/imdb_id`，否则订阅不可用。
- 详情页增强：演员表走**免 token** `GET /api/catalog/{category}/{uuid}/credit/`；相似推荐走 `GET /api/catalog/item/{uuid}/similar`（**需 OAuth2 Bearer**，无 token 401），因 `MediaInfo` 无该字段，以文本块注入 `mi.overview` 显示。配置项 `neodb_token` 留空则只显示演员表。

## 八、NeoDB 公开 API 能力边界（2026-07-31 实测）

- 只有 `GET /api/trending/{category}/`（book/game/movie/music/performance/podcast/tv），**每类仅 60 条，第 2 页起完全重复** → 「看不到全部」的真正根因，非 bug 非鉴权。
- **不存在** `/api/ranking/`、`/api/discover/`（404）。
- `/api/catalog/search`（公开，query 必填，每页 20 真分页）：只能搜不能无关键词浏览。缺 query→422，空→400。
- `/api/catalog/gallery/`（公开）：8 个策展合集，trending_movie/tv 与 trending 端点同一批，对影视零增量。
- `/api/catalog/fetch`（url 取单条）、`/api/catalog/{type}/{uuid}/credit/`（演职员，公开）。
- 鉴权仅开放 `me/tag/` 与 `similar`，**不提供 genre/年代/地区浏览**。
- 结论：NeoDB 只能做 60 条精选；要全量+多维筛选必须换源（TMDB Discover / 豆瓣）。

## 九、历史修复记录（要点）

- **ChineseSubFinder v6.0.2**：① 修 post_message 签名坑；② ERROR「调用 API 失败 HTTP 500: open ...nfo」根因是**时序竞态**（CSF 靠 Emby/Jellyfin 生成的 .nfo 取 id，TransferComplete 触发时 .nfo 未生成，约 1 分钟后才有）→ 改为后台线程 + 5xx/网络异常最多 5 次间隔 20s 重试，4xx 或耗尽才上报。
- **StuckDownloadGuard v1.1.0**：新增「降级切换」——先降级排队尾，再换源（订阅走 `SubscribeChain().search(sid)`，非订阅走 `SearchChain().search_by_title(title)` 跨索引器取做种最多者 + `DownloadChain().download_single(context=..., torrent_content=..., label=settings.TORRENT_TAG)`），每卡顿周期仅切换一次，无效则停止清理。配置项 `switch_source` 默认 True。
- 已发布：`NeoDBSource` v1.0.4、`ChineseSubFinder` v6.0.2、`StuckDownloadGuard` v1.1.0、`JackettExtend` v6.0.2、`ProwlarrExtend` v6.0.0、`JackettIndexer` v6.1.0、`LunaTVSource` v0.4.84、`SiteOpenSignup`。
