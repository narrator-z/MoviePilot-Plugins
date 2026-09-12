# MoviePilot-Plugins 项目长期记忆

> 细节过程见 `.workbuddy/memory/YYYY-MM-DD.md` 日志；本文件只保留长期有效的硬规则与已实证结论。

## 一、插件开发硬规则

1. **版本号双字段同步**：`__init__.py` 的 `plugin_version` ↔ `package*.json` 的 `version`（基础索引 + 对应 flag 清单）必须一起改。不 bump 市场不会推送更新（改行为就必须 bump）。
2. **清单条目必须有同名代码目录**；**v3-only 插件只进 `package.json` + `package.v3.json`，不进 v2 清单**。基础索引条目要带 `"v3": true` + `system_version`。
3. **改 `plugin_author` 前先 grep 是否被业务逻辑引用**（JackettIndexer 拿它当域名占位符，须等于 `plugin_author.lower()`）。
4. `py_compile` 查不出运行期 NameError；改完必须在容器内 import 验证（或跑桩化单测驱动真实代码路径）。
5. 插件不显示/装不上：查 `/config/logs/moviepilot.log` 的「加载插件 X 失败」；Market 安装失败文件留在 `/config/plugins_backup`。
6. **fork 镜像内置插件 shadow Market 副本**：`/app/app/plugins/<id>/` 优先于 `/config/plugins/<id>/`，改代码要 docker cp 到内置路径（后者只是数据目录）。
7. **post_message 新签名**：只能 `post_message(mtype=, title=, text=, source=)`；禁止传 Notification 对象（会被当 channel 而崩溃）。
8. **v2/v3 同名插件必须逐行 diff 对齐**（v3 特有适配除外）。发版前必做：
   `diff <(tr -d '\r' < plugins.v2/<p>/__init__.py) <(tr -d '\r' < plugins.v3/<p>/__init__.py)`（**必须 `tr -d '\r'`**）+ 跑 `.workbuddy/repo_audit.py`。
   ⚠️ **定性别急着上 P0**：先做影响面实测。
9. **「签名收了参数、函数体却不用」是最危险的半截改动** → 用 `.workbuddy/unused_arg_scan.py`（AST）扫。判据：**只有 v2 用了 / v3 没用才算 bug**；v2/v3 成对出现属宿主接口约定。
10. **验证"改了没生效"要直查容器**：`docker exec moviepilot grep -n <新行特征> /app/app/plugins/<id>/<file>`。
11. **Jackett torznab 只认 query 里的 `apikey`**，cookie/header 一律无效。
12. ⚠️ **并行 Edit 会静默覆盖**：同一条消息里对**同一文件**发多个 Edit 时，后写的可能覆盖前一个；**改完必须 grep 确认内容落盘**。

## 二、仓库与插件市场

- 三份索引：`package.json`（无 VERSION_FLAG 实例读）、`package.v2.json`、`package.v3.json`；Market 按插件 ID 跨仓库去重、**版本高者胜出**；市场页排除「已安装且无更新」→ 条数少于清单正常。
- 清单 key 是**首字母大写**插件名（`LunaTVSource`）。history 行 6 空格缩进，最后一条需补尾逗号。
  ⚠️ **v2 索引 history key 带 `v` 前缀**（`v1.1.1`），base/v3 **不带**（`1.1.1`）。
- 发版校验：比对 清单 version/author ↔ 代码 `plugin_version`/`plugin_author` ↔ 目录集合（正则 `^\s*字段名\s*=`）。
- 已发布（作者统一 `narrator-z`）：LunaTVSource 0.4.87、ChineseSubFinder 6.0.2、StuckDownloadGuard **1.1.3**、JackettExtend 6.0.3、ProwlarrExtend 6.0.0、JackettIndexer 6.1.0、NeoDBSource 1.0.4、SiteOpenSignup。
- 仅 lunatvsource 有**内部 `package.json`**（含 version），其余插件没有 → 别去找。

## 三、NAS / 部署环境

- SSH `narratorz@192.168.31.145:22022`，key `~/.ssh/id_ed25519_1panel`；容器 **`moviepilot`**（host 网络，后端 47901）。
- 路径：插件 `/config/plugins/<id>/`、日志 `/config/logs/moviepilot.log`、DB `/config/user.db`。
- 部署：scp → `docker cp` → 清 `__pycache__` → `docker restart moviepilot`（30–60s 后看日志）。
- 容器内跑脚本：`docker exec -i moviepilot python3 - < script.py`；应用工厂 **`app.factory.create_app()`**。
- **本机出不了外网** → git push 走 **NAS 中继**：`git bundle create <f>.bundle main`（要在**仓库目录内**生成）→ scp 到 NAS `/tmp` → `git clone` + `fetch bundle` + `merge --ff-only FETCH_HEAD` + `push` → 本机 `git update-ref refs/remotes/origin/main <sha>`。
- ⚠️ 本机 bash 偶发 PATH 为空：命令前补 `export PATH="/c/Users/tutu-work/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"`。

## 四、宿主目录 / 分类决策（插件改动必须遵守）

- 入口 `DirectoryHelper().get_dir(media, storage, src_path, target_storage, dest_path)`：
  - 传 `dest_path` → 只留 `library_path == dest_path`（手动整理语义）；
  - **传 `src_path` → 候选收窄到「包含该源路径的下载目录」**，不匹配**直接返回 None**（陷阱）；
  - 都不传 → 按 `media_match_rank`（固定分类 0/1 > 仅类型 2 > 无类型 3）+ `priority`。
- ⇒ **插件整理必须显式传 `target_directory = get_dir(media)`**，别依赖宿主自算。
- 传 `target_directory` 后宿主还读 `library_path / transfer_type / renaming / overwrite_mode / notify / scraping`：
  **`library_path` 空 → ValueError**；**`transfer_type` 空 → 「未设置整理方式」**；`scrape` 传 **None** 才跟随目录设置，传 False 会覆盖关闭刮削。
- 分类事实要求 **`media_source` 与 `media_id` 同时完整**，否则 `state=not_evaluated`。⚠️ **`MediaInfo(tmdb_info=payload)` 的 `__post_init__` 会用 tmdb_info 重投影身份**：payload 无 `"id"` 时身份被清成 None → 分类失败。**用宿主 `recognize_media()` 的返回对象最稳**。
- `recognize_media` 每次重跑 `classification_service.finalize()` → 用户改策略/目录立即生效；⚠️ **`finalize(media)` 返回新对象**，不会原地挂 `classification`。
- `manual_transfer` 不接受 `mediainfo`，`do_transfer` 接受 → 统一 `do_transfer`（给了 `target_directory` 天然绕过 `src_path` 收窄）。
- 下载侧 `get_download_dir_by_save_path` **仅当 save_path 精确等于某配置下载目录根**才命中。
- 分类对象（v3.0.37）：`media.classification = ClassificationResult{recommended, effective, labels, policy_revision, state}`；`effective = ClassificationSelection{category_id, category_path, rule_id, source}` ⇒ 展示名取 **`effective.category_path`**，策略版本在 **result 级 `policy_revision`**。

## 五、LunaTVSource（fork 维护）

- **v3-only**；上游基线 **0.4.59（03b0fd2）**，本分支定制**仅 `cms.py` 两处**（`_normalize_cms_title()` 把 【…】/[…] 转 (…)）。
- 与上游比较**必须用 difflib `splitlines()`**，不能用 `diff` 命令（core.autocrlf 会让整文件判为全等差异）。
- **0.4.85 起「整理落点」交宿主分类决策**：`recognize_media()` → 显式 `target_directory = get_dir(media)` + `target_path=None` 调 `do_transfer`；旧逻辑抽 `_legacy_native_transfer()` 兜底。
- 「下载失败自动换源」0.4.86 起、0.4.87 增强：候选表必须建在 `matching_results[:1]` 截断【之前】（唯一位置敏感点）；入队写 `task.alt_urls`；`_requeue_with_fallback` 取下一个未试地址；**有界**（每 url 至多一次）；仅 `source_strategy` 非 `all` 生效。单测 `.workbuddy/luna_fallback_test.py`。
- **0.4.88 无进展看门狗**：用 `DownloadTask.last_progress_at`；`_reap_stalled_tasks()` 只发中止信号，状态迁移交给 worker；由定时服务 `run_queue()`（每 1 分钟）驱动；配置 `stall_timeout_minutes` 默认 15（0–240，0=关闭）。LunaTVSource 是镜像内置插件，源码在 `/app/app/plugins/lunatvsource/`。
- 源列表在 `plugindata.luna_source_config_v1`；CMS 搜索 `?ac=list&wd=&pg=`、详情 `?ac=detail&ids=`；`vod_play_url` 用 `$$$` 分线路、`#` 分集、`$` 分名称/URL。

## 六、下载守卫 StuckDownloadGuard（1.1.3 起，v2/v3 完全同源逐行一致）

- 宿主接口（容器内实测对齐）：`SubscribeChain().search(sid=)`/`.get_subscribe_by_source()`、`SearchChain().search_by_title(title=, sites=None, cache_local=False)`、`DownloadChain().download_single(context=, torrent_content=, label=)`、`DownloadHistoryOper().get_by_hashes/get_by_hash/delete_history`（返回 `Dict[str,DownloadHistory]`，**PK=`id`**）、`SystemConfigOper().get(SystemConfigKey.Downloaders)`、`settings.TORRENT_TAG`。
- **状态分类**：`_QB_ACTIVE_STATES`(downloading/stalleddl/metadl/forceddl/checkingdl/allocating)、`_QB_QUEUED_STATES`(queueddl)、`_QB_FAULT_STATES`(error/missingfiles/unknown)。卡顿判定 `stuck = (active or fault) and dl_speed<=0`。
- **1.1.3 行为**：
  - 异常态（error/缺文件/unknown）僵尸种子：**立即**停止并清理（订阅源顺带重搜），不走重试观察窗口。
  - 活跃卡顿：按有无做种人分流——**无做种人**（`num_seeds==0`）直接尝试换源/清理，跳过 30min×重试 的空等；**有做种人**先降级排尾重试，重试无效（默认 3 次）再换源→失败清理。
  - `stoppedup`（完成做种 100%）/ 暂停 / 排队 不误伤。
- ⚠️ 排查「下载中不动」姿势：①查插件副本版本（有无 .pyc=真加载）；②查 `systemconfig.plugin.<ID>` 的 enabled/cron/only_subscribe；③查 `plugindata.torrent_states`（`{}`=监控跑过但无种子进监控）；④直连下载器列 state×进度交叉表。`only_subscribe=true` 会把无 `Subscribe|` 来源的卡死种子全跳过。
- **下载守卫只管 qBittorrent/Transmission 种子，管不到 LunaTVSource 的 m3u8 下载（另一条通道，有自己的换源）。**
- 单测 `.workbuddy/sdg_stuck_test.py`（桩化 `app.*` + `importlib` 载入源码，**40 用例全过**）。

## 七、transferhistory / 空间核算（inode 视角）

- 存量归位后 `transferhistory.dest` **不会自动更新**，要手动重写（**只改 dest 侧**；`src`/`downloadhistory.path`/`downloadfiles.*`/`transfersettlementreceipt.src` 是下载侧事实，改了即伪造）。`dest_fileitem` 的 path/name/basename/extension/size/modify_time 要与 dest 一起改。
- ⚠️ **`du -sh a b c` 跨参数按 inode 去重**：link 模式与下载源同 inode → 严重低估。多目录占用必须逐个单独 du。
- 回收区释放量远小于表面值：link 模式下删回收区几乎不腾空间，要回收须连下载源一起清（删源不影响库）。
- 清理核算：候选集合内每个 inode，**候选之外无引用**（`nlink - 候选内出现次数 == 0`）才真释放。活动下载目录（如 `/media/m3u8`）**绝不能整个删**。
- Emby 刷新：`POST http://192.168.31.145:8096/Library/Refresh` + `X-Emby-Token: <apikey>` → 204。

## 八、常见故障入口

- **订阅搜到资源但下不动**：先查 `systemconfig.Downloaders` 里目标下载器 **`enabled: false`**（`app/chain/download/submission.py:500` 返回「未找到下载器」）。自带下载通道的插件（LunaTVSource 走 m3u8 直下）不受影响 → 表现为「插件在动、种子订阅全停」，别误判成插件故障。**改 `systemconfig` 后必须 `docker restart moviepilot`**（内存缓存），改前备份 `user.db`。
- **媒体库存量归位审计金标准**：比对 `transferhistory` 的 `category`（MP 算的正确分类）与 `dest`（实际落盘），前缀不一致=落盘错。
- 分类策略**没有兜底规则**：`origin_country` 不在白名单（如 CO）→ 落「未分类」，是正确行为不是 bug。
- `/media` 是单一 ext4 挂载点 → 库内搬迁是原子 rename（零搬运）；`transfer_type=link` 硬链接 link count=2，**删库内副本不影响下载源，反之亦然**。

## 九、其他坑位

- NeoDBSource：必须经 `get_module()` 注册 recognize 且**只处理本源**；须从 `external_resources[]` 提取 tmdb/douban/imdb 写入 `MediaInfo`，否则订阅不可用。公开 API 只有 `trending/{category}`/`catalog/search`/`gallery/`/`fetch`/`credit`。
- `MediaInfo.year` 是 **str**（`int()` 触发 500）；`MediaType` 枚举值是**中文**（`MediaType.MOVIE.value == "电影"`）。
- 列表缩略图优先取 `poster_path`（只设 `cover` 会空白）。
- 图片代理已配 `IMAGE_PROXY_ALLOWED_PRIVATE_RANGES` 覆盖 clash fake-ip，测试别硬传 None。
