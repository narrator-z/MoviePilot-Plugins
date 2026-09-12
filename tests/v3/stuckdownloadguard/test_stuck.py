# -*- coding: utf-8 -*-
"""
下载卫士（StuckDownloadGuard）卡顿处理逻辑 L1 单测（纯本地、不联网、不触盘、不依赖容器）

背景：1.1.0 存在两个缺陷
  D1 卡顿判定要求 progress < 0.1%，「中途卡住」（如下到 50% 却 0 速度）完全不被接管；
  D2 换源时机反了——一卡住就尝试换源，且 switch_attempted 置 True 后永不重置，
     若首次因瞬时抖动失败就再也不会换源，只能干等 max_retries 到顶。

1.1.3 行为（异常态立即清 / 活跃卡顿按有无做种人分流）：
  - 异常态（error/缺文件/unknown）僵尸：一经发现立即停止并清理，不进重试窗口；
  - 活跃卡顿 + 无做种人：达时长后直接换源/清理，跳过无意义的降级重试；
  - 活跃卡顿 + 有做种人：先降级排尾重试，重试无效（达 max_retries）才换源，换源失败才清理。
"""
import sys
import types
import importlib.util
import os


# ---------------------------------------------------------------- 桩：app.* 依赖
def _mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _Logger:
    def __init__(self):
        self.lines = []

    def _log(self, lvl, msg, *a):
        self.lines.append(f"[{lvl}] {msg}")

    def info(self, m, *a): self._log("INFO", m)
    def debug(self, m, *a): self._log("DEBUG", m)
    def warning(self, m, *a): self._log("WARN", m)
    def error(self, m, *a): self._log("ERROR", m)


LOGGER = _Logger()
_mod("app", __path__=[])
_mod("app.log", logger=LOGGER)
_mod("app.chain")
_mod("app.chain.subscribe", SubscribeChain=object)
_mod("app.chain.download", DownloadChain=object)
_mod("app.chain.search", SearchChain=object)
_mod("app.db")
_mod("app.db.oper")


class _DownloadHistoryOper:
    def get_by_hashes(self, hashes): return {}
    def get_by_hash(self, h): return None
    def delete_history(self, hid): return True


_mod("app.db.oper.downloadhistory", DownloadHistoryOper=_DownloadHistoryOper)
_mod("app.db.oper.systemconfig", SystemConfigOper=object)
_mod("app.helper")
_mod("app.helper.thread", ThreadHelper=object)


class _Settings:
    TORRENT_TAG = "MOVIEPILOT"
    TZ = "Asia/Shanghai"


_mod("app.sdk")
_mod("app.sdk.config", settings=_Settings())


class _NotificationType:
    Plugin = "plugin"


class _SystemConfigKey:
    Downloaders = "Downloaders"


class _MediaType:
    def __init__(self, v): self.value = v


_mod("app.schemas")
_mod("app.schemas.types", NotificationType=_NotificationType,
     SystemConfigKey=_SystemConfigKey, MediaType=_MediaType)


class _PluginBase:
    def get_data(self, key): return None
    def save_data(self, key, value): return True
    def update_config(self, cfg): return True
    def post_message(self, **kw): return True


_mod("app.plugins", _PluginBase=_PluginBase)

# 桩：第三方
sys.modules.setdefault("pytz", _mod("pytz", timezone=lambda tz: None))
_mod("apscheduler")
_mod("apscheduler.schedulers")
_mod("apscheduler.schedulers.background", BackgroundScheduler=object)
_mod("apscheduler.triggers")
_mod("apscheduler.triggers.cron", CronTrigger=object)

# ---------------------------------------------------------------- 载入插件源码
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC = os.path.join(ROOT, "plugins.v3", "stuckdownloadguard", "__init__.py")
spec = importlib.util.spec_from_file_location("sdg_guard", SRC)
sdg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdg)
Guard = sdg.StuckDownloadGuard

# ---------------------------------------------------------------- 测试骨架
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   -> {detail}" if detail and not cond else ""))


def make_guard(max_retries=3, switch_source=True):
    g = Guard()
    g._enabled = True
    g._onlyonce = False
    g._inactive_minutes = 0          # 立即触发，便于测试
    g._max_retries = max_retries
    g._only_subscribe = False
    g._delete_files = False
    g._delete_history = True
    g._notify = True
    g._switch_source = switch_source
    g._states = {}
    g._scheduler = None
    # 记录各类动作调用
    g.calls = {"demote": 0, "switch": 0, "escalate": 0, "notify": []}
    g.switch_result = False

    def _demote(clients, downloader, hash_str):
        g.calls["demote"] += 1
        return True

    def _switch(hash_str, rec, t, clients):
        g.calls["switch"] += 1
        return g.switch_result

    def _escalate(clients, downloader, hash_str, rec):
        g.calls["escalate"] += 1

    def _notify(action, title, hash_str, extra=""):
        g.calls["notify"].append({"action": action, "extra": extra})

    setattr(g, "_StuckDownloadGuard__demote_and_move_tail", _demote)
    setattr(g, "_StuckDownloadGuard__switch_source", _switch)
    setattr(g, "_StuckDownloadGuard__escalate", _escalate)
    setattr(g, "_StuckDownloadGuard__notify", _notify)
    return g


def torrent(progress, speed, state="stalleddl", dtype="qbittorrent", h="h1", num_seeds=5):
    return {
        "hash": h, "title": "测试剧集 S01E01", "downloader": "qb",
        "type": dtype, "raw_state": state, "progress": progress, "dl_speed": speed,
        "num_seeds": num_seeds,
    }


print("=" * 74)
print("A. 卡顿判定：中途卡住（进度 50%、速度 0）应被接管  [修复 D1]")
print("=" * 74)

g = make_guard()
t_mid = torrent(progress=50.0, speed=0)
setattr(g, "_StuckDownloadGuard__collect", lambda: ([t_mid], {}))
g.monitor()
check("A1 中途卡住(50%)被判定为卡死并进入处理", len(g.calls["notify"]) == 1,
      f"notify={g.calls['notify']}")
if g.calls["notify"]:
    check("A2 通知文案标注「中途卡住」", "中途卡住" in g.calls["notify"][0]["extra"],
          g.calls["notify"][0]["extra"])
check("A3 状态已建立 retries=1", g._states.get("h1", {}).get("retries") == 1,
      str(g._states))

print()
print("=" * 74)
print("B. 0 进度卡住仍照常接管（回归，不应被改坏）")
print("=" * 74)
g = make_guard()
setattr(g, "_StuckDownloadGuard__collect", lambda: ([torrent(progress=0.0, speed=0)], {}))
g.monitor()
check("B1 0 进度卡住被接管", len(g.calls["notify"]) == 1)
check("B2 文案标注「0 进度卡住」", "0 进度卡住" in g.calls["notify"][0]["extra"],
      g.calls["notify"][0]["extra"])

print()
print("=" * 74)
print("C. 正常下载（速度>0）不应被接管（防误伤）")
print("=" * 74)
g = make_guard()
setattr(g, "_StuckDownloadGuard__collect", lambda: ([torrent(progress=50.0, speed=1024)], {}))
g.monitor()
check("C1 速度>0 不进入监控", g._states == {} and g.calls["notify"] == [], str(g._states))

print()
print("=" * 74)
print("D. 重试窗口：未达上限时只降级重试、不动用换源  [修复 D2 时机]")
print("=" * 74)
g = make_guard(max_retries=3, switch_source=True)
g._states["h1"] = {"title": "T", "downloader": "qb", "active_stuck": 0.0,
                   "last_ts": None, "retries": 0}
setattr(g, "_StuckDownloadGuard__collect", lambda: ([torrent(progress=50.0, speed=0)], {}))
for i in range(2):
    g.monitor()      # 第 1、2 轮：重试窗口
check("D1 两轮均执行降级", g.calls["demote"] == 2, str(g.calls["demote"]))
check("D2 未达上限前不触发换源", g.calls["switch"] == 0, str(g.calls["switch"]))
check("D3 未达上限前不触发停止清理", g.calls["escalate"] == 0, str(g.calls["escalate"]))
check("D4 通知为「重试中」", all("重试中" in n["action"] for n in g.calls["notify"]),
      str(g.calls["notify"]))

print()
print("=" * 74)
print("E. 重试无效（达上限）→ 切换下载源；成功则停止追踪原种子")
print("=" * 74)
g = make_guard(max_retries=3, switch_source=True)
g.switch_result = True
g._states["h1"] = {"title": "T", "downloader": "qb", "active_stuck": 0.0,
                   "last_ts": None, "retries": 2}   # 第 3 轮即达上限
setattr(g, "_StuckDownloadGuard__collect", lambda: ([torrent(progress=50.0, speed=0)], {}))
g.monitor()
check("E1 达上限后触发换源", g.calls["switch"] == 1, str(g.calls["switch"]))
check("E2 换源成功则不执行停止清理", g.calls["escalate"] == 0, str(g.calls["escalate"]))
check("E3 换源成功后移除原种子追踪", "h1" not in g._states, str(g._states))

print()
print("=" * 74)
print("F. 重试无效 + 换源失败 → 升级为停止/清理（中途卡住也会走到换源）")
print("=" * 74)
g = make_guard(max_retries=3, switch_source=True)
g.switch_result = False
g._states["h1"] = {"title": "T", "downloader": "qb", "active_stuck": 0.0,
                   "last_ts": None, "retries": 2}
setattr(g, "_StuckDownloadGuard__collect", lambda: ([torrent(progress=50.0, speed=0)], {}))
g.monitor()
check("F1 达上限后尝试换源（失败）", g.calls["switch"] == 1)
check("F2 换源失败后升级为停止清理", g.calls["escalate"] == 1, str(g.calls["escalate"]))
check("F3 清理后移除追踪", "h1" not in g._states)

print()
print("=" * 74)
print("G. 关闭「自动切换下载源」→ 达上限直接停止清理，不换源")
print("=" * 74)
g = make_guard(max_retries=2, switch_source=False)
g._states["h1"] = {"title": "T", "downloader": "qb", "active_stuck": 0.0,
                   "last_ts": None, "retries": 1}
setattr(g, "_StuckDownloadGuard__collect", lambda: ([torrent(progress=50.0, speed=0)], {}))
g.monitor()
check("G1 不触发换源", g.calls["switch"] == 0, str(g.calls["switch"]))
check("G2 直接停止清理", g.calls["escalate"] == 1, str(g.calls["escalate"]))

print()
print("=" * 74)
print("H. 换源不再被「一次性标记」卡死（D2：首次失败后仍可在后续周期重试）")
print("=" * 74)
g = make_guard(max_retries=1, switch_source=True)
g.switch_result = False           # 首次换源失败
g._states["h1"] = {"title": "T", "downloader": "qb", "active_stuck": 0.0,
                   "last_ts": None, "retries": 0}
setattr(g, "_StuckDownloadGuard__collect", lambda: ([torrent(progress=50.0, speed=0)], {}))
g.monitor()                        # 第 1 周期：换源失败→清理
check("H1 第1周期尝试换源", g.calls["switch"] == 1)
# 模拟换源后新种子再次卡住（新 hash），应重新走完整流程而非被标记禁用
g.switch_result = True
g._states["h2"] = {"title": "T2", "downloader": "qb", "active_stuck": 0.0,
                   "last_ts": None, "retries": 0}
setattr(g, "_StuckDownloadGuard__collect",
        lambda: ([torrent(progress=30.0, speed=0, h="h2")], {}))
g.monitor()
check("H2 后续周期仍可换源（无一次性标记残留）", g.calls["switch"] == 2, str(g.calls["switch"]))
check("H3 状态字典不再含 switch_attempted 残留字段",
      "switch_attempted" not in g._states.get("h2", {}), str(g._states))

print()
print("=" * 74)
print("I. 异常态（error / missingFiles）僵尸任务：一经发现立即清理（不进重试窗口）")
print("=" * 74)
# 现场实证：qBittorrent 里 2 个 error + 1 个 missingfiles 常年停在 0%，
# 旧版因不在 _QB_ACTIVE_STATES 内而永远无人处理；1.1.2 起纳入 fault，1.1.3 改为立即清理。
for st in ["error", "missingfiles", "unknown"]:
    g = make_guard()
    setattr(g, "_StuckDownloadGuard__collect",
            lambda s=st: ([torrent(progress=0.0, speed=0, state=s)], {}))
    g.monitor()
    check(f"I-{st} 异常态被立即接管(无需等待)", len(g.calls["notify"]) == 1, str(g.calls["notify"]))
    if g.calls["notify"]:
        check(f"I-{st} 文案标注异常态", "异常态" in g.calls["notify"][0]["extra"],
              g.calls["notify"][0]["extra"])
    check(f"I-{st} 异常态直接执行清理(不重试)", g.calls["escalate"] == 1, str(g.calls["escalate"]))
    check(f"I-{st} 异常态不进入降级重试", g.calls["demote"] == 0, str(g.calls["demote"]))

print()
print("=" * 74)
print("K. 活跃卡顿 + 无做种人：达时长后直接换源/清理，跳过降级重试空等")
print("=" * 74)
g = make_guard(max_retries=3, switch_source=True)
g.switch_result = True
setattr(g, "_StuckDownloadGuard__collect",
        lambda: ([torrent(progress=0.0, speed=0, state="stalleddl", num_seeds=0)], {}))
g.monitor()
check("K1 无做种人直接尝试换源(不重试)", g.calls["switch"] == 1, str(g.calls["switch"]))
check("K2 无做种人不执行降级排尾", g.calls["demote"] == 0, str(g.calls["demote"]))
check("K3 换源成功则清理原种子", g.calls["escalate"] == 0 and "h1" not in g._states,
      f"escalate={g.calls['escalate']} states={list(g._states)}")

print()
print("=" * 74)
print("K'. 活跃卡顿 + 无做种人 + 换源失败：直接升级为停止清理")
print("=" * 74)
g = make_guard(max_retries=3, switch_source=True)
g.switch_result = False
setattr(g, "_StuckDownloadGuard__collect",
        lambda: ([torrent(progress=50.0, speed=0, state="stalleddl", num_seeds=0)], {}))
g.monitor()
check("K'1 换源失败后直接清理", g.calls["escalate"] == 1, str(g.calls["escalate"]))
check("K'2 不浪费降级重试", g.calls["demote"] == 0, str(g.calls["demote"]))
check("K'3 清理后移除追踪", "h1" not in g._states)

print()
print("=" * 74)
print("J. 已完成做种(stoppedup)不应被误伤（现场 281 个此类）")
print("=" * 74)
g = make_guard()
setattr(g, "_StuckDownloadGuard__collect",
        lambda: ([torrent(progress=100.0, speed=0, state="stoppedup")], {}))
g.monitor()
check("J1 stoppedup 不进入监控", g._states == {} and g.calls["notify"] == [], str(g._states))

print()
print("=" * 74)
print(f"结果: {len(PASS)} 通过 / {len(FAIL)} 失败")
print("=" * 74)
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("ALL PASS")
