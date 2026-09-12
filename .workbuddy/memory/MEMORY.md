# MoviePilot-Plugins 项目长期记忆

> 细节过程见 `.workbuddy/memory/YYYY-MM-DD.md` 日志；本文件只保留长期有效的硬规则与已实证结论。

## 一、插件开发硬规则

1. **版本号双字段同步**：`__init__.py` 的 `plugin_version` 与 `package*.json` 的 `version`（基础索引 + 对应 flag 清单）必须一起改。
2. **清单条目必须有同名代码目录**；**v3-only 插件只进 `package.v3.json` + 基础索引，不进 v2 清单**。基础索引条目要带 `"v3": true` + `system_version`。
3. **改 `plugin_author` 前先 grep 是否被业务逻辑引用**（JackettIndexer 拿它当域名占位符，必须等于 `plugin_author.lower()`）。
4. `py_compile` 查不出运行期 NameError；改完必须在容器内 import 验证。
5. 插件不显示/装不上：查 `/config/logs/moviepilot.log` 的「加载插件 X 失败」；Market 安装失败的文件会留在 `/config/plugins_backup`。
6. **fork 镜像内置插件 shadow Market 副本**：`/app/app/plugins/<id>/` 优先于 `/config/plugins/<id>/`，改代码要 docker cp 到内置路径。
7. **post_message 新签名**：只能 `post_message(mtype=..., title=..., text=..., source=...)`；禁止传 Notification 对象（会被当 channel 传入而崩溃）。
8. **v2/v3 同名插件必须逐行 diff 对齐**（v3 特有适配除外）。`2028bf9` 提交信息写"v2/v3 同改"，实际 v3 只改了**函数签名 + 调用点**、**函数体漏改** → 修复从未生效、三天无人发现（已于 `9470f54` 修，版本 6.0.3）。
   发版前必做：`diff <(tr -d '\r' < plugins.v2/<p>/__init__.py) <(tr -d '\r' < plugins.v3/<p>/__init__.py)`（**必须 `tr -d '\r'`**，否则 core.autocrlf 让全文件被判为差异）+ 跑 `.workbuddy/repo_audit.py`。
   ⚠️ **定性别急着上 P0**：该漏改实测**无功能影响**（见第 11 条 torznab 鉴权），属"一致性 + 潜在风险"级 P1。发现漏改要先做**影响面实测**再定级。
9. **「签名收了参数、函数体却不用」是最危险的半截改动**（读签名觉得传了、读调用点觉得拿到了，只有函数体知道它扔了）。用 `.workbuddy/unused_arg_scan.py`（AST）扫。
   判据：**只有 v2 用了 / v3 没用才算 bug**；v2/v3 成对出现的属宿主接口签名约定（`search_torrents(page/cat)`、`refresh_torrents(keyword/cat/mtype)`、`recognize_media(mtype)`、`media_path(root)`、`cleanup_task(output_parent)` 均已确认为无害）。
10. **验证"代码改了没生效"要直查容器**：`docker exec moviepilot grep -n <新行特征> /app/app/plugins/<id>/<file>`。市场落点就是 `/app/app/plugins/<id>/`（`/config/plugins/<id>/` 只是数据目录）。
11. **Jackett torznab 只认 query 里的 `apikey`，cookie / header 一律无效**（2026-09-12 鉴权矩阵实测）。
    ⇒ 任何"补 cookie/header 才能搜"的假设都要先实测；`RequestUtils(headers=…, cookies=…)` 传了也不影响结果。
    判定某鉴权改动有没有用，唯一判据是**直接发请求对比响应**，不是读代码。

## 二、仓库与插件市场

- 三份索引：`package.json`（无 VERSION_FLAG 实例读）、`package.v2.json`、`package.v3.json`；Market 按插件 ID 跨仓库去重、**版本高者胜出**。
- 市场页会排除「已安装且无更新」的条目 → 看到条数少于清单是正常的，不是 bug。
- 发版校验脚本必做：比对 清单 version/author ↔ 代码 `plugin_version`/`plugin_author` ↔ 目录集合；正则用 `^\s*字段名\s*=`（类变量有缩进）。
- 已发布：LunaTVSource 0.4.86(OneBigMoon)、ChineseSubFinder 6.0.2、StuckDownloadGuard 1.1.0、JackettExtend 6.0.3、ProwlarrExtend 6.0.0、JackettIndexer 6.1.0、NeoDBSource 1.0.4、SiteOpenSignup。
- 清单条目 key 是**首字母大写**的插件名（`LunaTVSource`），不是目录名 `lunatvsource`；改清单时按 `      "0.4.8x": `（6 空格缩进）定位 history 行，最后一条 history 需要补尾逗号。

## 三、LunaTVSource（fork 维护）

- **v3-only**（无 `plugins.v2/lunatvsource`）；上游基线 **0.4.59（03b0fd2）**，本分支定制**仅 `cms.py` 两处**（`_normalize_cms_title()` 把片名 【…】/[…] 转成 (…)）。
- 与上游比较**必须用 difflib 的 `splitlines()`**，不能用 `diff` 命令（`core.autocrlf` 会让整文件被判为全等差异）。
- 同步策略：版本差距大时直接**上游整目录替换 + 重贴 2 处定制**（含 ai/cms/downloader/m3u8_engine/naming/classification/dist/vendor）。
- 部署后用插件目录里有没有 `.pyc` 判断插件是否真被加载（比翻日志可靠）。
- **0.4.85 起「整理落点」完全交给宿主分类决策**（见 §五）：媒体身份 → 宿主 `recognize_media()` 取带 tmdb 事实的 MediaInfo → 显式 `target_directory = get_dir(media)` + `target_path=None` 调 `do_transfer`；旧的自选目录逻辑抽成 `_legacy_native_transfer()` 仅作兜底。相关改动集中在 `__init__.py`，`cms.py` 两处 fork 定制未动。
- 验证插件改动**不必也不许改 `/app`**：把整目录传到容器 `/tmp/lunaprobesrc/`，脚本里 `sys.path.insert(0,"/tmp/lunaprobesrc")` **最后插入**（否则被 `/app/app/plugins` 抢先），即可 import 新版；再用桩替换 `_HostMediaChain/_HostTransferChain/_HostStorageChain` 断言整理入口实际传参。

## 四、NAS / 部署环境

- SSH `narratorz@192.168.31.145:22022`，key `~/.ssh/id_ed25519_1panel`；容器 **`moviepilot`**（host 网络，后端 47901）。
- 插件目录 `/config/plugins/<id>/`，日志 `/config/logs/moviepilot.log`，DB `/config/user.db`。
- 部署：scp → `docker cp` 进容器 → 清 `__pycache__` → `docker restart moviepilot`（30–60s 后看日志）。
- 容器内跑脚本：`docker exec -i moviepilot python3 - < script.py`；应用工厂 **`app.factory.create_app()`**。
- 离线复现目录/分类逻辑：`app.factory.create_app()` + monkeypatch `DirectoryHelper.get_dirs = staticmethod(lambda: [TransferDirectoryConf(**d) for d in <db Directories>])`。
- 宿主数据位置：`MediaInfo` 在 **`app.domain.context`**；`TransferDirectoryConf` 在 `app.schemas.system`；目录助手 `app.application.directory`；分类策略 `systemconfig['MediaClassificationPolicy']['active']`（内容嵌在 `active` 下）。
- **本机出不了外网** → git push 走 **NAS 中继**（bundle → scp → NAS clone/merge/push → 本机 `git update-ref`）。
- ⚠️ 本机 bash 偶发 PATH 为空（`dirname`/`tail` not found）：命令前补 `export PATH="/c/Users/tutu-work/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"`。

## 五、宿主目录 / 分类决策（2026-09-12 实证，插件改动必须遵守）

- 唯一正确入口 `DirectoryHelper().get_dir(media, storage, src_path, target_storage, dest_path)`：
  - 传 `dest_path` → 只保留 `library_path == dest_path` 的目录（手动整理语义）；
  - **传 `src_path` → 候选被收窄到「包含该源路径的下载目录」**，分类不匹配时**直接返回 None**（陷阱，导致整理被拒）；
  - 都不传 → 全量目录按 `media_match_rank`（固定分类 0/1 > 仅类型 2 > 无类型 3）+ `priority` 选。
- ⇒ **插件整理必须显式传 `target_directory = get_dir(media)`**，不能依赖宿主自算：一旦下载根落在某个已配置下载目录内（例如清空 `download_root` 后取到「国漫」目录），宿主自己算就会返回 None。
- 传 `target_directory` 后宿主还会读它的 `library_path / transfer_type / renaming / overwrite_mode / notify / scraping`：
  - **`library_path` 为空 → 抛 ValueError**；**`transfer_type` 为空 → 抛「未设置整理方式」** → 插件必须预先过滤/兜底；
  - `scrape` 传 None 才跟随目录设置，传 False 会**覆盖并关闭**用户目录里配的刮削。
- 分类事实构造要求 **`media_source` 与 `media_id` 同时完整**，否则抛 ValueError → `state=not_evaluated`（不报错但没分类）。
- ⚠️ **`MediaInfo(tmdb_info=payload)` 的 `__post_init__` 会用 `tmdb_info` 重投影身份与事实：payload 里没有 `"id"` 时 `media_source`/`media_id` 会被清成 None** → 分类直接失败。用宿主 `recognize_media()` 的返回对象最稳（它自带完整 tmdb_info 与身份）。
- `extensions.themoviedb.*` **只来自 `media.tmdb_info`**；`genre_keys` 来自 `genres[].name`/`genre_ids`。影视规则全部 `sources=['themoviedb']`。
- `recognize_media` 每次都会重跑 `classification_service.finalize()`（`refresh` 被忽略），缓存命中也不会带旧分类 → **用户改策略/目录立即生效**。
- `manual_transfer` **不接受** `mediainfo`；`do_transfer` 接受 → 统一用 `do_transfer`。给了 `target_directory` 后 execution 的 `if not task.target_directory` 短路，天然绕过 `src_path` 收窄。
- 下载侧：`get_download_dir_by_save_path(media, save_path)` **仅当 save_path 精确等于某个配置下载目录的「根」**时命中，再用 `build_media_download_path(root, dir, media, helper)` 追加分类子目录；未注册根 / 子目录 / 固定分类目录 → 不命中，原样使用（这是宿主原生语义）。
- fork 定制 `_degrade_missing_category_to_root`：无分类时关掉 `library_category_folder` → 落到媒体库根，**不丢文件**。
- `monitor_type=None`（不监控）的目录会被 `get_dir` 跳过 → 全部如此时 `get_dir` 返回 None（插件第二跳 `include_unsorted=True` 可放宽，严格优于旧「按目录名猜」）。
- ⚠️ **`ClassificationExecutionService.finalize(media)` 返回的是新对象**，不会原地给传入 media 挂 `classification`（返回对象是 MediaInfo 的副本 + `.classification`）。所以要么用返回值，要么直接用宿主 `recognize_media()` 的返回对象（它内部已 finalize）。
- 分类对象结构（v3.0.37 实测）：`media.classification` = `ClassificationResult{recommended, effective, labels, policy_revision, state}`；`effective` = `ClassificationSelection{category_id, category_path, rule_id, source}`。⇒ 取展示名要用 **`effective.category_path`**，策略版本号在 **result 级 `policy_revision`**（不在 effective 上）。

## 六、探索页自定义数据源（NeoDBSource）

- 必须经 `get_module()` 注册 recognize 方法，**只处理本源**、其余返回 None（否则抢在 TMDB/豆瓣前赢者通吃）。
- 从 `external_resources[]` 提取 tmdb/douban/imdb 写入 `MediaInfo`，否则订阅不可用。
- 公开 API 只有 `trending/{category}`（每类 60 条、第 2 页起重复）、`catalog/search`、`gallery/`、`fetch`、`credit`；无 ranking/discover、无维度浏览。

## 七、transferhistory 历史同步与空间核算（2026-09-12 实证）

- 存量文件归位/搬迁后，`transferhistory.dest` **不会自动更新**，要手动重写：
  `/media/link/animes/国漫/<条目>` → `/media/link/shows/<该行 category>/<条目>`（category 列本身就是对的，按行推导即可）。
- 文件名三态：`exact`（同名还在）/ `rematched`（归位时同集被替换 → 在同季目录按 `SxxExx` 找真实文件）/ `missing`（已进回收区）。
  `dest_fileitem` 的 path/name/basename/extension/size/modify_time 必须与 dest 一起改。实测 122 行：34/88/0。
- **只改 dest 侧**；`src`、`downloadhistory.path`、`downloadfiles.*`、`transfersettlementreceipt.src` 是下载侧事实，改了就成伪造。
  `systemconfig.Directories` 是目录配置本身、`mediaserveritem.path` 是 Emby 同步缓存，都不该动。
- ⚠️ **`du -sh a b c` 跨参数按 inode 去重**：库是 link 模式与下载源同 inode，一起统计会严重低估（实测 58G 被报成 16G）。**多目录占用必须逐个单独 du**。
- 💡 回收区能释放的空间远小于表面值：`/media/_recycle_20260912` 47.2G 中仅 **4.3G 独占**，**42.9G 与下载源共享 inode**
  → 只删回收区几乎不腾空间，要回收必须连下载源一起清（link 模式下清源不影响库）。
- 查询"某路径还有谁引用"：遍历 `sqlite_master` 各表各列 `CAST(col AS TEXT) LIKE '%路径片段%'`，比逐表翻可靠。

## 八、订阅「搜到资源但下不动」= 先查下载器开关（2026-09-12 实证）

- 症状：订阅/搜索有结果，但没有任何下载动作；`downloadfailure` 里成片 `error_message = 未找到下载器`。
- 根因入口：`systemconfig` 的 **`Downloaders`** 里目标下载器的 **`enabled: false`**（可能还伴随 `default: false`）。
  取不到可用下载器时 `app/chain/download/submission.py:500` 直接返回「未找到下载器」。
- ⚠️ **自带下载通道的插件不受影响**：LunaTVSource 走自己的 m3u8 直下 + 自整理，不经下载器
  → 表现为「插件在动、种子订阅全停」，极易误判成插件故障。**先看 `Downloaders` 再看插件。**
- 排查顺序：`downloadfailure` 按 `error_message` 聚合 → `systemconfig.Downloaders` 看 `enabled` →
  用 curl 直连下载器验证服务本身（qBittorrent：`/api/v2/app/version?apikey=…` 返版本即在线）。
- **改 `systemconfig` 后必须 `docker restart moviepilot`**（内存缓存），改前先 `cp /config/user.db /config/user.db.bak-<用途>-<日期>`。

## 九、清理释放量按 inode 核算，别按目录大小

- 库（link 模式）与下载源是**同一 inode 的硬链接** → 只删一侧不释放空间。
- 判定：候选集合内每个 inode，若**候选之外无引用**（`nlink - 候选内出现次数 == 0` 且不在保留集合）才会真释放。
- 实测：回收区 47.17G + 旧源 57.42G（表面 104.6G），**同时删**只释放 **约 42G**；
  旧源里 15.3G 与库共享，删源后库仍引用 → 永久不释放（磁盘上本就只占一份）。
- **活动下载目录绝不能整个删**（如 LunaTVSource 的 `download_root=/media/m3u8`）。脚本必须显式排除。

## 十、LunaTVSource「下载失败自动换源」（0.4.86 已实现）

### 实现要点（改 3 处，`__init__.py` + `downloader.py`）

- **配置**：`source_fallback`（VSwitch，默认**开**；旧配置缺键按开处理）、
  `fallback_max_sources`（VTextField 0–5，默认 **2**，`0` = 关闭换源）。
  读取侧 `_source_fallback_enabled()` / `_fallback_max_sources()` 都带缺键/坏值兜底。
- **候选表必须建在 `matching_results[:1]` 截断【之前】**（`__init__.py` ≈5507–5513）：
  `_collect_episode_candidates()` 把每一集在**全部**匹配源上的播放地址收成 `{(season,episode): [url,…]}`（同址去重保序）。
  截断后只剩排名第一的源，备选地址会在那一行被永久丢弃 —— 这是整个功能唯一的"位置敏感"点。
- **入队带候选**：构造 `DownloadTask` 时剔除当前 `url`、截断到上限，写 `task.alt_urls`。
- **失败轮转**：`_finish_failed` 开头，`control.action == ""`（**非**用户暂停/删除）时调
  `_requeue_with_fallback(task, error)`：把当前 url 记入 `failed_urls`，取 `alt_urls` 中第一个未试过的地址，
  置 `pending` + 换 `url`，`progress/attempts/output/downloaded_bytes/download_engine` 全部复位。
- **幂等且有界**：每个 url 至多尝试一次（`failed_urls` 去重集合）；候选耗尽才写终态 `failed`，
  失败通知带「（已尝试 N 个源均失败）」。换源中途是另一条通知「LunaTV 自动换源」，
  正文只打印 host（`_url_host`），**不泄露完整播放链接**。
- **`enqueue()` 复用失败任务时也换源**：先 `_merge_fallback_urls` 并入本次扫描新发现的备选，再取下一个未试地址，
  而不是照抄那个已知失效的 URL。
- **数据兼容**：`DownloadTask` 新增 `alt_urls` / `failed_urls`（`default_factory=list`），
  `_download_task_from_payload` 校验必须是 `str` 列表，老记录缺字段即空列表 = 无备选 = 旧行为。
- **仅 `source_strategy` 非 `all` 时生效**：`all` 本身多源并行入队，不存在"换"；且 `all` 下
  `source_key = result.source_key` → `identity_key` 源相关，不同源本就是不同任务。
- **L1 单测**：`.workbuddy/luna_fallback_test.py`，28 用例（I1 同 identity 不新增任务 / I2 每候选至多一次 /
  I3 耗尽才终态 / I5 老记录兼容 / I6 重启不丢进度）。默认导入**仓库源码**；容器内验证改后副本设 `LUNA_SRC=/tmp/luna_new`。

### 为什么必须这么改（旧版行为与误判清单）

- 旧版失败链路：`_finish_failed` 只置 `state=failed` + 通知，**无换源分支**。
- ⭐ **失败任务复用 ≠ 换源**：`enqueue()` 本可把 failed 重置为 pending 并写新 URL，但
  `_rank_subscription_results` 排序键（新季>集数>分辨率>原始顺序）**完全确定性、不含失败因子**，
  ⇒ 每轮算出同一名次、同一 URL。线上实测**重试 31 次仍是同一主机** = 无换源的铁证。
- 易被误认成换源的机制（都不是）：m3u8 列表 `range(2)` 同 URL 重试（**403 不可重试**）、
  `--download-retry-count 3`、多引擎回退 `for engine in self._m3u8_engines`（**只注册 1 个引擎**，空架子）、
  写库 `range(2)`、`fallback_sources.json`（源清单离线兜底）、`_rank_subscription_results`（**下载前**择优）。
  `downloader.py:1685` 的「using ffmpeg」是遗留误导文案。
- 源列表在 `plugindata.luna_source_config_v1`（值是**列表**，元素 `key/name/api/detail`）；
  CMS 接口：搜索 `?ac=list&wd=&pg=`、详情 `?ac=detail&ids=`；`vod_play_url` 用 `$$$` 分线路、`#` 分集、`$` 分名称/URL。

## 十一、其他坑位

- `MediaInfo.year` 是 **str**（`int()` 会触发 response_model 校验 500）；`MediaType` 枚举值是**中文**（`MediaType.MOVIE.value == "电影"`）。
- 列表缩略图优先取 `poster_path`（只设 `cover` 会空白）。
- 图片代理已配 `IMAGE_PROXY_ALLOWED_PRIVATE_RANGES` 覆盖 clash fake-ip，测试时别硬传 None。

## 十二、媒体库存量归位（2026-09-12 已执行）

- **审计金标准**：`transferhistory` 同表存 `category`（MP 算出的正确分类）与 `dest`（实际落盘）。
  `category` 与 `dest` 前缀不一致 = 该次整理落盘错了。查"整理对不对"**先跑这个一致性比对**，
  比任何事后推断都可靠（本次 122/122 全不一致，聚合成 9 部剧）。
- **分类策略没有兜底规则**：`MediaClassificationPolicy.active.rules[].when` 条件为——
  国漫 = animation 且 origin_country∈{CN,TW,HK}；日番 = animation 且 JP；
  国产剧 = {CN,TW,HK}；欧美剧 = {US,FR,GB,DE,ES,IT,NL,PT,RU,UK}；日韩剧 = JP/KR；
  纪录片/儿童/综艺 看 genre；动画电影 看 animation；华语电影 看 original_language∈{zh,cn,bo,za}。
  ⇒ **origin_country 不在白名单（如 CO 哥伦比亚）→ 无规则匹配 → 落"未分类"，这是正确行为，不是 bug。**
- **`/media` 是单一 ext4 挂载点** → 库内搬迁为原子 rename（零数据搬运）。库 `transfer_type=link`
  → 硬链接 link count=2：**删库内副本不影响下载源，删源也不影响库**（互为独立目录项）。
- **归位取舍规则**（脚本 `.workbuddy/reorganize_lunatv.py`，带 dry-run、回收区而非直接删）：
  `score = 体积，非 mp4 再 ×1.5`；同集由 score 大者占位。效果 = 跨格式时保住带字幕 mkv，
  同格式时才按体积替换。执行结果：补入 85 文件/70G、回收 167 文件/47.2G、替换 6、删目录 13。
- Emby 刷新：`POST http://192.168.31.145:8096/Library/Refresh` + header `X-Emby-Token: <apikey>` → 204。
  Emby 侧看到的是宿主路径 `/vol2/1000/Media/...`，旧路径条目会在扫描后自动移除。
