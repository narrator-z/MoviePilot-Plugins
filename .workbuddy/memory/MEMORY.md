# MoviePilot-Plugins 项目长期记忆

> 细节过程见 `.workbuddy/memory/YYYY-MM-DD.md` 日志；本文件只保留长期有效的硬规则与已实证结论。

## 一、插件开发硬规则

1. **版本号双字段同步**：`__init__.py` 的 `plugin_version` ↔ `package*.json` 的 `version`（基础索引 + 对应 flag 清单）必须一起改。**不 bump 市场不会推送更新**（改行为就必须 bump）。
2. **清单条目必须有同名代码目录**；**v3-only 插件只进 `package.json` + `package.v3.json`，不进 v2 清单**。基础索引条目要带 `"v3": true` + `system_version`。
3. **改 `plugin_author` 前先 grep 是否被业务逻辑引用**（JackettIndexer 拿它当域名占位符，须等于 `plugin_author.lower()`）。
4. `py_compile` 查不出运行期 NameError；改完必须在容器内 import 验证（或直接跑桩化单测驱动真实代码路径）。
5. 插件不显示/装不上：查 `/config/logs/moviepilot.log` 的「加载插件 X 失败」；Market 安装失败的文件留在 `/config/plugins_backup`。
6. **fork 镜像内置插件 shadow Market 副本**：`/app/app/plugins/<id>/` 优先于 `/config/plugins/<id>/`，改代码要 docker cp 到内置路径（后者只是数据目录）。
7. **post_message 新签名**：只能 `post_message(mtype=, title=, text=, source=)`；禁止传 Notification 对象（会被当 channel 而崩溃）。
8. **v2/v3 同名插件必须逐行 diff 对齐**（v3 特有适配除外）。发版前必做：
   `diff <(tr -d '\r' < plugins.v2/<p>/__init__.py) <(tr -d '\r' < plugins.v3/<p>/__init__.py)`（**必须 `tr -d '\r'`**）+ 跑 `.workbuddy/repo_audit.py`。
   历史教训 `2028bf9` 声称同改、实际 v3 只改签名+调用点、函数体漏改（已 `9470f54` 修）。⚠️ **定性别急着上 P0**：先做影响面实测。
9. **「签名收了参数、函数体却不用」是最危险的半截改动** → 用 `.workbuddy/unused_arg_scan.py`（AST）扫。判据：**只有 v2 用了 / v3 没用才算 bug**；v2/v3 成对出现属宿主接口约定（`search_torrents(page/cat)` 等均已确认无害）。
10. **验证"改了没生效"要直查容器**：`docker exec moviepilot grep -n <新行特征> /app/app/plugins/<id>/<file>`。
11. **Jackett torznab 只认 query 里的 `apikey`**，cookie/header 一律无效。判定鉴权改动有没有用，唯一判据是**直接发请求对比响应**。

## 二、仓库与插件市场

- 三份索引：`package.json`（无 VERSION_FLAG 实例读）、`package.v2.json`、`package.v3.json`；Market 按插件 ID 跨仓库去重、**版本高者胜出**；市场页排除「已安装且无更新」→ 条数少于清单是正常的。
- 清单 key 是**首字母大写**插件名（`LunaTVSource`）。history 行 6 空格缩进，最后一条需补尾逗号。
  ⚠️ **v2 索引 history key 带 `v` 前缀**（`v1.1.1`），base/v3 **不带**（`1.1.1`）。
- 发版校验：比对 清单 version/author ↔ 代码 `plugin_version`/`plugin_author` ↔ 目录集合（正则 `^\s*字段名\s*=`，类变量有缩进）。
- 已发布：LunaTVSource 0.4.87、ChineseSubFinder 6.0.2、StuckDownloadGuard **1.1.1**、JackettExtend 6.0.3、ProwlarrExtend 6.0.0、JackettIndexer 6.1.0、NeoDBSource 1.0.4、SiteOpenSignup。作者**全部统一为 `narrator-z`**（LunaTVSource 原 OneBigMoon 已改；`project_url`/`plugin_icon` 仍指上游，属资源引用非作者身份）。
- 仅 lunatvsource 有**内部 `package.json`**（含 version），其余插件没有 → 别去找。

## 三、NAS / 部署环境

- SSH `narratorz@192.168.31.145:22022`，key `~/.ssh/id_ed25519_1panel`；容器 **`moviepilot`**（host 网络，后端 47901）。
- 路径：插件 `/config/plugins/<id>/`、日志 `/config/logs/moviepilot.log`、DB `/config/user.db`。
- 部署：scp → `docker cp` → 清 `__pycache__` → `docker restart moviepilot`（30–60s 后看日志）。
- 容器内跑脚本：`docker exec -i moviepilot python3 - < script.py`；应用工厂 **`app.factory.create_app()`**。
- 离线复现目录/分类逻辑：`create_app()` + monkeypatch `DirectoryHelper.get_dirs`。
- 宿主数据位置：`MediaInfo` 在 `app.domain.context`；`TransferDirectoryConf` 在 `app.schemas.system`；目录助手 `app.application.directory`；分类策略 `systemconfig['MediaClassificationPolicy']['active']`（内容嵌在 `active` 下）。
- **本机出不了外网** → git push 走 **NAS 中继**：`git bundle create <f>.bundle main`（要在**仓库目录内**生成，写到用户目录会静默不落盘）→ scp 到 NAS `/tmp` → `git clone` + `fetch bundle` + `merge --ff-only FETCH_HEAD` + `push` → 本机 `git update-ref refs/remotes/origin/main <sha>`。
- ⚠️ 本机 bash 偶发 PATH 为空：命令前补 `export PATH="/c/Users/tutu-work/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"`。

## 四、宿主目录 / 分类决策（插件改动必须遵守）

- 入口 `DirectoryHelper().get_dir(media, storage, src_path, target_storage, dest_path)`：
  - 传 `dest_path` → 只留 `library_path == dest_path`（手动整理语义）；
  - **传 `src_path` → 候选收窄到「包含该源路径的下载目录」**，不匹配**直接返回 None**（陷阱）；
  - 都不传 → 按 `media_match_rank`（固定分类 0/1 > 仅类型 2 > 无类型 3）+ `priority`。
- ⇒ **插件整理必须显式传 `target_directory = get_dir(media)`**，别依赖宿主自算（下载根落在已配下载目录内时宿主自算会返回 None）。
- 传 `target_directory` 后宿主还读 `library_path / transfer_type / renaming / overwrite_mode / notify / scraping`：
  **`library_path` 空 → ValueError**；**`transfer_type` 空 → 「未设置整理方式」** → 插件须预过滤；`scrape` 传 **None** 才跟随目录设置，传 False 会覆盖关闭刮削。
- 分类事实要求 **`media_source` 与 `media_id` 同时完整**，否则 `state=not_evaluated`（不报错但没分类）。
  ⚠️ **`MediaInfo(tmdb_info=payload)` 的 `__post_init__` 会用 tmdb_info 重投影身份**：payload 无 `"id"` 时身份被清成 None → 分类失败。**用宿主 `recognize_media()` 的返回对象最稳**。
- `recognize_media` 每次重跑 `classification_service.finalize()`（`refresh` 被忽略）→ 用户改策略/目录立即生效。
  ⚠️ **`finalize(media)` 返回新对象**，不会原地挂 `classification`。
- `manual_transfer` 不接受 `mediainfo`，`do_transfer` 接受 → 统一 `do_transfer`（给了 `target_directory` 天然绕过 `src_path` 收窄）。
- 下载侧 `get_download_dir_by_save_path` **仅当 save_path 精确等于某配置下载目录的根**才命中 → 未注册根/子目录原样使用（宿主原生语义）。
- `monitor_type=None` 目录会被 `get_dir` 跳过 → 全如此则返回 None（插件第二跳 `include_unsorted=True` 可放宽）。
- 分类对象（v3.0.37）：`media.classification = ClassificationResult{recommended, effective, labels, policy_revision, state}`；`effective = ClassificationSelection{category_id, category_path, rule_id, source}` ⇒ 展示名取 **`effective.category_path`**，策略版本在 **result 级 `policy_revision`**。
- `extensions.themoviedb.*` 只来自 `media.tmdb_info`；`genre_keys` 来自 `genres[].name`/`genre_ids`；影视规则全部 `sources=['themoviedb']`。

## 五、LunaTVSource（fork 维护）

- **v3-only**；上游基线 **0.4.59（03b0fd2）**，本分支定制**仅 `cms.py` 两处**（`_normalize_cms_title()` 把片名 【…】/[…] 转成 (…)）。
- 与上游比较**必须用 difflib `splitlines()`**，不能用 `diff` 命令（core.autocrlf 会让整文件判为全等差异）。版本差距大时直接上游整目录替换 + 重贴 2 处定制。
- 部署后用插件目录里有没有 `.pyc` 判断是否真被加载（比翻日志可靠）。
- **0.4.85 起「整理落点」交给宿主分类决策**：宿主 `recognize_media()` → 显式 `target_directory = get_dir(media)` + `target_path=None` 调 `do_transfer`；旧逻辑抽成 `_legacy_native_transfer()` 兜底。
- 验证改动**不必也不许改 `/app`**：整目录传容器 `/tmp/lunaprobesrc/`，脚本里 `sys.path.insert(0, "/tmp/lunaprobesrc")` **最后插入**（否则被 `/app/app/plugins` 抢先），再桩掉 `_HostMediaChain/_HostTransferChain/_HostStorageChain` 断言实际传参。
- 「下载失败自动换源」0.4.86 起、0.4.87 增强（跨源活链解析）。要点：
  - **候选表必须建在 `matching_results[:1]` 截断【之前】**（≈5507–5513）—— 截断后备选地址被永久丢弃，这是唯一位置敏感点。
  - 入队写 `task.alt_urls`（0.4.87 起先过健康探针挑活链）；失败时 `_requeue_with_fallback` 取下一个未试地址，`progress/attempts` 复位。
  - **有界**：每 url 至多一次（`failed_urls`），耗尽才终态。0.4.87 增加失败用尽后跨所有源重搜 + 探针筛活链（**网络 I/O 必须在 `_lock` 外**；解析器异常吞掉退化为旧终态，绝不无限重搜）。
  - **仅 `source_strategy` 非 `all` 生效**（`all` 本就多源并行）。
  - 单测 `.workbuddy/luna_fallback_test.py`（36 用例，全过）。
- 源列表在 `plugindata.luna_source_config_v1`（值是列表）；CMS：搜索 `?ac=list&wd=&pg=`、详情 `?ac=detail&ids=`；`vod_play_url` 用 `$$$` 分线路、`#` 分集、`$` 分名称/URL。

## 六、下载守卫 StuckDownloadGuard（1.1.1 起）

- **v2/v3 必须逐行一致**（该插件两端完全同源，无 v3 特有适配）；无内部 package.json。
- 宿主接口（容器内实测对齐）：`SubscribeChain().search(sid=)` / `.get_subscribe_by_source()`、`SearchChain().search_by_title(title=, sites=None, cache_local=False)`、`DownloadChain().download_single(context=, torrent_content=, label=)`、`DownloadHistoryOper().get_by_hashes/get_by_hash/delete_history`（返回 `Dict[str,DownloadHistory]`，**PK=`id`**）、`SystemConfigOper().get(SystemConfigKey.Downloaders)`、`settings.TORRENT_TAG`。
- **1.1.1 行为（重试 → 换源 → 清理）**：
  - 卡顿判定 `stuck = active and dl_speed <= 0`（**不区分进度**：0 进度与中途卡住同样接管）。`is_zero` 仅用于通知文案。
    暂停 `pausedDL`/排队 `queueddl`/做种不在 `_QB_ACTIVE_STATES` 内 → 不误伤。
  - 每轮降级排尾（重试窗口）；`retries >= max_retries` 才调 `__switch_source`（订阅走订阅链重搜、非订阅跨索引器重搜更优种子并替换）；换源失败才 `__escalate`（停止清理，订阅源顺带重搜）。
  - **已移除 `switch_attempted` 一次性标记**（旧版置 True 后永不重置 → 首次瞬时失败就再也不换源）。旧持久化残留该字段无害。
- 单测 `.workbuddy/sdg_stuck_test.py`（21 用例全过）。
- 💡 **可复用：插件桩化单测手法**（纯本地、不联网不触盘）：用 `sys.modules` 注入假 `app.*`（`app.log/app.chain.*/app.db.*/app.helper.thread/app.plugins._PluginBase/app.core.config.settings/app.schemas.types`）+ `pytz`/`apscheduler`，再 `importlib.util.spec_from_file_location` 载入插件源码，即可驱动 `monitor()` 与私有方法（打桩要用名称改写后的名字：`setattr(g, "_StuckDownloadGuard__switch_source", stub)`）。比"只能进容器 import"更快且能断言分支行为。

## 七、transferhistory / 空间核算（inode 视角）

- 存量文件归位后 `transferhistory.dest` **不会自动更新**，要手动重写（`/media/link/animes/国漫/<条目>` → `/media/link/shows/<category>/<条目>`，category 列本身是对的）。
  **只改 dest 侧**；`src`、`downloadhistory.path`、`downloadfiles.*`、`transfersettlementreceipt.src` 是下载侧事实，改了就是伪造。`dest_fileitem` 的 path/name/basename/extension/size/modify_time 要与 dest 一起改。
- ⚠️ **`du -sh a b c` 跨参数按 inode 去重**：库是 link 模式与下载源同 inode → 严重低估（58G 被报 16G）。**多目录占用必须逐个单独 du**。
- 💡 回收区释放量远小于表面值：47.2G 中仅 4.3G 独占、42.9G 与下载源共享 inode → 只删回收区几乎不腾空间，要回收必须连下载源一起清（link 模式下清源不影响库）。
- 清理核算：候选集合内每个 inode，**候选之外无引用**（`nlink - 候选内出现次数 == 0`）才真释放。实测回收区+旧源表面 104.6G，同删只释放约 42G。**活动下载目录（如 `/media/m3u8`）绝不能整个删**，脚本须显式排除。
- 查"某路径还有谁引用"：遍历 `sqlite_master` 各表各列 `CAST(col AS TEXT) LIKE '%路径片段%'`。

## 八、常见故障入口

- **订阅搜到资源但下不动**：先查 `systemconfig.Downloaders` 里目标下载器 **`enabled: false`**（`app/chain/download/submission.py:500` 返回「未找到下载器」）。**自带下载通道的插件（LunaTVSource 走 m3u8 直下）不受影响** → 表现为「插件在动、种子订阅全停」，别误判成插件故障。**改 `systemconfig` 后必须 `docker restart moviepilot`**（内存缓存），改前备份 `user.db`。
- **媒体库存量归位审计金标准**：比对 `transferhistory` 的 `category`（MP 算的正确分类）与 `dest`（实际落盘），前缀不一致 = 落盘错了（本次 122/122 全不一致）。
- 分类策略**没有兜底规则**：`origin_country` 不在白名单（如 CO）→ 落「未分类」，是正确行为不是 bug。
- `/media` 是单一 ext4 挂载点 → 库内搬迁是原子 rename（零搬运）；`transfer_type=link` 硬链接 link count=2，**删库内副本不影响下载源，反之亦然**。
- 归位脚本 `.workbuddy/reorganize_lunatv.py`（dry-run + 进回收区而非直接删）：`score = 体积，非 mp4 再 ×1.5`。
- Emby 刷新：`POST http://192.168.31.145:8096/Library/Refresh` + `X-Emby-Token: <apikey>` → 204。

## 九、其他坑位

- 探索页自定义数据源（NeoDBSource）：必须经 `get_module()` 注册 recognize 且**只处理本源**（否则抢在 TMDB/豆瓣前赢者通吃）；须从 `external_resources[]` 提取 tmdb/douban/imdb 写入 `MediaInfo`，否则订阅不可用。公开 API 只有 `trending/{category}`（每类 60 条、第 2 页起重复）、`catalog/search`、`gallery/`、`fetch`、`credit`。
- `MediaInfo.year` 是 **str**（`int()` 触发 500）；`MediaType` 枚举值是**中文**（`MediaType.MOVIE.value == "电影"`）。
- 列表缩略图优先取 `poster_path`（只设 `cover` 会空白）。
- 图片代理已配 `IMAGE_PROXY_ALLOWED_PRIVATE_RANGES` 覆盖 clash fake-ip，测试别硬传 None。
