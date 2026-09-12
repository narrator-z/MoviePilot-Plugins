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

## 二、仓库与插件市场

- 三份索引：`package.json`（无 VERSION_FLAG 实例读）、`package.v2.json`、`package.v3.json`；Market 按插件 ID 跨仓库去重、**版本高者胜出**。
- 市场页会排除「已安装且无更新」的条目 → 看到条数少于清单是正常的，不是 bug。
- 发版校验脚本必做：比对 清单 version/author ↔ 代码 `plugin_version`/`plugin_author` ↔ 目录集合；正则用 `^\s*字段名\s*=`（类变量有缩进）。
- 已发布：LunaTVSource 0.4.85(OneBigMoon)、ChineseSubFinder 6.0.2、StuckDownloadGuard 1.1.0、JackettExtend 6.0.2、ProwlarrExtend 6.0.0、JackettIndexer 6.1.0、NeoDBSource 1.0.4、SiteOpenSignup。
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

## 七、其他坑位

- `MediaInfo.year` 是 **str**（`int()` 会触发 response_model 校验 500）；`MediaType` 枚举值是**中文**（`MediaType.MOVIE.value == "电影"`）。
- 列表缩略图优先取 `poster_path`（只设 `cover` 会空白）。
- 图片代理已配 `IMAGE_PROXY_ALLOWED_PRIVATE_RANGES` 覆盖 clash fake-ip，测试时别硬传 None。
