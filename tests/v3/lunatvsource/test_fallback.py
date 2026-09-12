"""LunaTVSource「下载失败自动换源」L1 单元测试。

不联网、不触盘、不碰 /app。默认导入仓库内源码；在容器内验证改后副本时，
设置环境变量 LUNA_SRC=/tmp/luna_new 即可。覆盖测试设计方案中的不变式
I1 / I2 / I3 / I5 / I6。
"""
import importlib
import json
import os
import sys
import threading
import time
import types

PKG = "luna_src"
SRC = os.environ.get("LUNA_SRC") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "plugins.v3",
    "lunatvsource",
)
pkg = types.ModuleType(PKG)
pkg.__path__ = [SRC]
sys.modules[PKG] = pkg
dl = importlib.import_module(f"{PKG}.downloader")

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \u2713 {name}")
    else:
        FAIL += 1
        print(f"  \u2717 {name}  {detail}")


print("=" * 72)
print("A. DownloadTask 新字段与向后兼容（I5/I6）")
print("=" * 72)
t = dl.DownloadTask(task_id="t1", source_key="lunatv", media_id="tmdb:1",
                    title="测试剧", year="2026", media_type="tv",
                    season=1, episode=1, url="http://a/1.m3u8", root="/tmp")
check("默认 alt_urls 为空列表", t.alt_urls == [], repr(t.alt_urls))
check("默认 failed_urls 为空列表", t.failed_urls == [], repr(t.failed_urls))

old_record = {
    "task_id": "t0", "source_key": "lunatv", "media_id": "tmdb:1", "title": "x",
    "year": "", "media_type": "tv", "season": 1, "episode": 1,
    "url": "http://a/1.m3u8", "root": "/tmp", "mode": "download",
    "ffmpeg_path": "ffmpeg", "state": "failed", "error": "",
    "control_action": "", "output": "", "download_engine": "",
}
back = dl._download_task_from_payload(dict(old_record))
check("改造前的老记录可正常反序列化（I5）", back.task_id == "t0")
check("老记录新字段回落为空（I5）", back.alt_urls == [] and back.failed_urls == [])

t.alt_urls = ["http://b/1.m3u8", "http://c/1.m3u8"]
t.failed_urls = ["http://a/1.m3u8"]
roundtrip = dl._download_task_from_payload(json.loads(json.dumps(t.to_dict())))
check("新字段序列化往返一致（I6）",
      roundtrip.alt_urls == t.alt_urls and roundtrip.failed_urls == t.failed_urls)

try:
    bad = dict(old_record)
    bad["alt_urls"] = "not-a-list"
    dl._download_task_from_payload(bad)
    check("非法 alt_urls 应被拒绝", False)
except ValueError:
    check("非法 alt_urls 被校验拒绝", True)

print()
print("=" * 72)
print("B. url 辅助函数")
print("=" * 72)
check("normalize 去重保序", dl._normalize_url_list(["a", "b", "a", "", "c"]) == ["a", "b", "c"])
check("merge 多组去重保序", dl._merge_fallback_urls(["a", "b"], ["b", "c"]) == ["a", "b", "c"])
check("next 跳过已试过的", dl._next_fallback_url(["a", "b", "c"], ["a"]) == "b")
check("next 用尽返回空串", dl._next_fallback_url(["a"], ["a", "b"]) == "")
check("host 提取（通知不泄露完整链接）",
      dl._url_host("http://svip.ryplay14.com/x/y/1.m3u8") == "svip.ryplay14.com")

print()
print("=" * 72)
print("C. 队列换源状态机（I1/I2/I3）")
print("=" * 72)


def make_queue():
    """裸实例：绕开 __init__ 的文件/缓存副作用，只用内存态。"""
    q = object.__new__(dl.DownloadQueue)
    state = {"tasks": []}
    q._load = lambda *a, **k: None
    q._save = lambda *a, **k: None
    q._notify = lambda title, body: notes.append((title, body))
    q._lock = threading.RLock()
    q._active = {}
    q._active_destinations = {}
    q._delete_file_tasks = set()
    q._running = False
    q._current_task_id = ""
    q._active_owner_id = None
    q._idle_event = threading.Event()
    q._drain_wakeup = threading.Event()
    q._read = lambda: [
        dl._download_task_from_payload(json.loads(json.dumps(x))) for x in state["tasks"]
    ]

    def _write(tasks):
        state["tasks"] = [x.to_dict() for x in tasks]

    q._write = _write
    return q, state


def seed(state, url, alts, failed=None, tid="t1", stable="failed"):
    task = dl.DownloadTask(task_id=tid, source_key="lunatv", media_id="tmdb:1",
                           title="剧", year="2026", media_type="tv",
                           season=1, episode=1, url=url, root="/tmp")
    task.alt_urls = list(alts)
    task.failed_urls = list(failed or [])
    task.state = stable
    state["tasks"] = [task.to_dict()]
    return task


notes = []
q, state = make_queue()

# --- 轮转 1：a 失败 -> 切 b ---
task = seed(state, "http://a/1.m3u8", ["http://b/1.m3u8", "http://c/1.m3u8"])
assert q._requeue_with_fallback(task, "HTTP 403")
row = state["tasks"][0]
check("第 1 次失败切到候选 b", row["url"] == "http://b/1.m3u8", row["url"])
check("失败地址 a 记入 failed_urls（I2）", row["failed_urls"] == ["http://a/1.m3u8"], row["failed_urls"])
check("任务退回 pending 而非终态（I3）", row["state"] == "pending", row["state"])
check("progress/attempts 复位", row["progress"] == 0.0 and row["attempts"] == 0)
check("发出换源通知", any("自动换源" in n[0] for n in notes))

# --- 轮转 2：b 也失败 -> 切 c ---
task = dl._download_task_from_payload(state["tasks"][0])
assert q._requeue_with_fallback(task, "HTTP 403")
row = state["tasks"][0]
check("第 2 次失败切到候选 c", row["url"] == "http://c/1.m3u8", row["url"])
check("failed_urls 累积不重复（I2）",
      row["failed_urls"] == ["http://a/1.m3u8", "http://b/1.m3u8"], row["failed_urls"])

# --- 轮转 3：c 也失败 -> 候选用尽，应返回 False（交回终态逻辑）---
task = dl._download_task_from_payload(state["tasks"][0])
ok3 = q._requeue_with_fallback(task, "HTTP 403")
row = state["tasks"][0]
check("候选用尽时返回 False（I3 反向）", ok3 is False)
check("用尽时不改动任务（仍指向 c/failed 计数 2）",
      row["url"] == "http://c/1.m3u8" and len(row["failed_urls"]) == 2, row)

# --- 无候选：立即 False ---
q2, state2 = make_queue()
task2 = seed(state2, "http://a/1.m3u8", [])
check("无候选时立即返回 False（单源场景行为同改造前）",
      q2._requeue_with_fallback(task2, "err") is False)

# --- 已试过的候选被跳过 ---
q3, state3 = make_queue()
task3 = seed(state3, "http://a/1.m3u8",
             ["http://a/1.m3u8", "http://b/1.m3u8"], failed=["http://a/1.m3u8"])
q3._requeue_with_fallback(task3, "err")
check("alt 里已试过的地址被跳过，选中未试的 b（I2）",
      state3["tasks"][0]["url"] == "http://b/1.m3u8", state3["tasks"][0]["url"])

# --- 候选全试完 -> 不得再轮转 ---
q3b, state3b = make_queue()
task3b = seed(state3b, "http://a/1.m3u8", ["http://b/1.m3u8"],
              failed=["http://a/1.m3u8", "http://b/1.m3u8"])
check("候选全部试过 -> 返回 False，落入终态（I2/I3）",
      q3b._requeue_with_fallback(task3b, "err") is False)

# --- 持久化往返：轮转状态不丢（I6）---
q4, state4 = make_queue()
task4 = seed(state4, "http://a/1.m3u8", ["http://b/1.m3u8", "http://c/1.m3u8"])
task4.state = "running"
state4["tasks"] = [task4.to_dict()]
q4._requeue_with_fallback(task4, "err")
reloaded = dl._download_task_from_payload(state4["tasks"][0])
check("重启后换源进度仍在（I6）",
      reloaded.url == "http://b/1.m3u8" and reloaded.failed_urls == ["http://a/1.m3u8"])

print()
print("=" * 72)
print("D. enqueue 复用失败任务时优先换源（I1）")
print("=" * 72)
q5, state5 = make_queue()
task5 = seed(state5, "http://a/1.m3u8", ["http://b/1.m3u8"], stable="failed")

fresh = dl.DownloadTask(task_id="brand-new", source_key="lunatv", media_id="tmdb:1",
                        title="剧", year="2026", media_type="tv",
                        season=1, episode=1, url="http://a/1.m3u8", root="/tmp")
fresh.alt_urls = ["http://b/1.m3u8"]
before = len(state5["tasks"])
q5.enqueue(fresh)
rows = state5["tasks"]
check("同 identity 不产生新任务（I1）", len(rows) == before == 1, f"len={len(rows)}")
check("复用失败任务并换到候选 b", rows[0]["url"] == "http://b/1.m3u8", rows[0]["url"])
check("复用后状态为 pending", rows[0]["state"] == "pending", rows[0]["state"])

# 无候选时保持旧行为（重试同一 url）
q6, state6 = make_queue()
seed(state6, "http://a/1.m3u8", [], stable="failed")
fresh6 = dl.DownloadTask(task_id="x", source_key="lunatv", media_id="tmdb:1",
                         title="剧", year="2026", media_type="tv",
                         season=1, episode=1, url="http://a/1.m3u8", root="/tmp")
q6.enqueue(fresh6)
check("无候选时复用仍用原 url（回归）",
      state6["tasks"][0]["url"] == "http://a/1.m3u8", state6["tasks"][0]["url"])

print()
print("=" * 72)
print("E. 跨源活链解析器接缝（增强换源覆盖）")
print("=" * 72)

# 解析器在被调用时应拿到 task，并返回活链列表；调用方会剔除已试过的。
def fake_resolver(t):
    return ["http://live1/1.m3u8", "http://live2/2.m3u8"]


qe, statee = make_queue()
task_e = seed(statee, "http://a/1.m3u8", [], failed=["http://a/1.m3u8"])
qe._fallback_resolver = fake_resolver
ok_e = qe._requeue_with_fallback(task_e, "HTTP 403")
row_e = statee["tasks"][0]
check("无入队候选时，跨源解析器注入活链并切到 live1", ok_e and row_e["url"] == "http://live1/1.m3u8", row_e)
check("解析器注入后任务退回 pending（非终态）", row_e["state"] == "pending", row_e["state"])
check("已试地址 a 进入 failed_urls（I2 不变式仍成立）", "http://a/1.m3u8" in row_e["failed_urls"], row_e)
check("live2 留在 alt_urls 待下次轮转", "http://live2/2.m3u8" in row_e["alt_urls"], row_e)

# 解析器返回的活链若已全部试过，应终止（不再无限重搜）
qe2, statee2 = make_queue()
task_e2 = seed(statee2, "http://a/1.m3u8", [], failed=["http://a/1.m3u8"])
qe2._fallback_resolver = lambda t: ["http://a/1.m3u8"]  # 只返回已试过的死链
ok_e2 = qe2._requeue_with_fallback(task_e2, "HTTP 403")
check("解析器只返回已试过的地址时返回 False（终态，不无限重搜）", ok_e2 is False)

# 解析器抛异常必须被吞掉，退化为原有终态逻辑
def boom(t):
    raise RuntimeError("network down")


qe3, statee3 = make_queue()
task_e3 = seed(statee3, "http://a/1.m3u8", [], failed=["http://a/1.m3u8"])
qe3._fallback_resolver = boom
ok_e3 = qe3._requeue_with_fallback(task_e3, "HTTP 403")
check("解析器异常被吞掉并返回 False（不崩溃、退化为终态）", ok_e3 is False)

# 解析器只在「入队候选用尽」后被调用：仍有入队候选时不应触发（且仍在锁外）
calls = []


def counting_resolver(t):
    calls.append(1)
    return ["http://live3/3.m3u8"]


qe4, statee4 = make_queue()
# 仍有入队候选 b -> 直接轮转到 b，跨源解析器根本不应被调用
task_e4 = seed(statee4, "http://a/1.m3u8", ["http://b/1.m3u8"], failed=["http://a/1.m3u8"])
qe4._fallback_resolver = counting_resolver
ok_e4 = qe4._requeue_with_fallback(task_e4, "err")
row_e4 = statee4["tasks"][0]
check("仍有入队候选时不触发跨源解析器（仅在用尽后）",
      ok_e4 and row_e4["url"] == "http://b/1.m3u8" and calls == [], row_e4)
check("未配置解析器时行为不变（回归）",
      make_queue()[0]._requeue_with_fallback(
          seed(make_queue()[1], "http://a/1.m3u8", []), "err") is False)

print()
print("=" * 72)
print("F. 无进展看门狗（下载中一直不动 → 中止并换源）")
print("=" * 72)


def make_watchdog(timeout_minutes=15.0, alts=("http://b/1.m3u8",),
                  seconds_idle=None, tid="tw", legacy_clock=False):
    """构造一个 running 任务 + 其 _TaskControl，模拟正在下载的状态。"""
    q, state = make_queue()
    q._stall_timeout_minutes = timeout_minutes
    q._last_stall_sweep = 0.0
    q._fallback_resolver = None
    q._pending_terminal = {}
    task = dl.DownloadTask(task_id=tid, source_key="lunatv", media_id="tmdb:1",
                           title="卡住的剧", year="2026", media_type="tv",
                           season=2, episode=3, url="http://a/1.m3u8", root="/tmp")
    task.state = "running"
    task.progress = 0.4
    task.alt_urls = list(alts)
    if not legacy_clock:
        # 进度最后一次推进是在 seconds_idle 之前
        task.last_progress_at = time.time() - (
            seconds_idle if seconds_idle is not None else (timeout_minutes * 60 + 60)
        )
    state["tasks"] = [task.to_dict()]
    control = dl._TaskControl()
    q._active[tid] = control
    return q, state, control


# F1 超时未推进 → 中止并请求换源
qf, sf, cf = make_watchdog(timeout_minutes=10, seconds_idle=15 * 60)
reaped = qf.reap_stalled_tasks()
check("进度静止超阈值 → 判定卡住（返回 1）", reaped == 1, reaped)
check("卡住任务被置 stall 中止信号", cf.action == "stall", cf.action)
check("中止信号已通知执行线程（event 已置位）", cf.event.is_set())

# F2 仍在推进 → 不中止
qf2, _sf2, cf2 = make_watchdog(timeout_minutes=10, seconds_idle=60)
check("未超阈值不中止（返回 0）", qf2.reap_stalled_tasks() == 0)
check("未超阈值时 action 保持为空", cf2.action == "", cf2.action)

# F3 关闭看门狗（0 分钟）→ 退回旧行为
qf3, _sf3, cf3 = make_watchdog(timeout_minutes=0, seconds_idle=99999)
check("stall_timeout=0 关闭看门狗（返回 0）", qf3.reap_stalled_tasks() == 0)
check("关闭时不做任何中止", cf3.action == "", cf3.action)

# F4 老任务无时钟 → 首次扫描只回填，不误杀
qf4, sf4, cf4 = make_watchdog(legacy_clock=True, tid="tlegacy")
check("老任务（无时钟）首次扫描不中止", qf4.reap_stalled_tasks() == 0)
check("老任务时钟被回填", sf4["tasks"][0]["last_progress_at"] > 0,
      sf4["tasks"][0].get("last_progress_at"))
check("老任务回填后 action 仍为空", cf4.action == "", cf4.action)
# 回填后再等一个超时周期才真正中止（复位扫描时钟以绕过节流）
qf4._last_stall_sweep = 0.0
sf4["tasks"][0]["last_progress_at"] = time.time() - 20 * 60
check("回填后再次静止才中止（返回 1）", qf4.reap_stalled_tasks() == 1)
check("回填后中止信号为 stall", cf4.action == "stall", cf4.action)

# F5 已有中止意图的任务不重复处理
qf5, _sf5, cf5 = make_watchdog(timeout_minutes=10, seconds_idle=99999)
cf5.action = "pause"
check("已有中止意图时跳过（返回 0）", qf5.reap_stalled_tasks() == 0)
check("已有中止意图不被覆盖为 stall", cf5.action == "pause", cf5.action)

# F6 非 running 状态不中止（不误伤 pending/paused）
qf6, sf6, cf6 = make_watchdog(timeout_minutes=10, seconds_idle=99999)
sf6["tasks"][0]["state"] = "pending"
check("非 running 任务不被看门狗中止", qf6.reap_stalled_tasks() == 0)
check("非 running 任务 action 保持为空", cf6.action == "", cf6.action)

# F7 引擎持续推进进度 → 刷新时钟，不判卡住
qf7, sf7, cf7 = make_watchdog(timeout_minutes=10, seconds_idle=99999)
qf7._update_progress("tw", 0.55)  # 有推进
check("进度推进后时钟被刷新",
      sf7["tasks"][0]["last_progress_at"] > time.time() - 30,
      sf7["tasks"][0].get("last_progress_at"))
check("持续推进的任务不被中止", qf7.reap_stalled_tasks() == 0)

# F8 进度封顶 0.99 仍视为存活（N_m3u8DL-RE 会把投影钳到 0.99）
qf8, sf8, cf8 = make_watchdog(timeout_minutes=10, seconds_idle=99999, tid="tsat")
qf8._update_progress("tsat", 0.99)
check("进度封顶 0.99 仍刷新时钟（下载未结束时不算卡住）",
      sf8["tasks"][0]["last_progress_at"] > time.time() - 30,
      sf8["tasks"][0].get("last_progress_at"))
check("封顶任务不被误判卡住", qf8.reap_stalled_tasks() == 0)

# F9 扫描节流：同一窗口内重复调用不再读队列
qf9, _sf9, cf9 = make_watchdog(timeout_minutes=10, seconds_idle=99999, tid="tthr")
first = qf9.reap_stalled_tasks()
check("首次扫描生效", first == 1, first)
cf9.action = ""  # 手动复位以观察节流（正常流程由 worker 消费）
check("节流窗口内二次扫描被跳过（返回 0）", qf9.reap_stalled_tasks() == 0)

# F10 _finish_stalled 有候选 → 回到 pending 并换 url（走有界轮转）
qf10, sf10, cf10 = make_watchdog(timeout_minutes=10, seconds_idle=99999,
                                 alts=("http://b/1.m3u8", "http://c/1.m3u8"),
                                 tid="tsw")
qf10.reap_stalled_tasks()
task_f10 = qf10._read()[0]
result = qf10._finish_stalled(task_f10, cf10)
row_f10 = next(x for x in sf10["tasks"] if x["task_id"] == "tsw")
check("卡住换源后回到 pending", result["state"] == "pending", result)
check("卡住换源切到备选地址", row_f10["url"] == "http://b/1.m3u8", row_f10["url"])
check("卡住的当前地址计入 failed_urls（每源至多一次）",
      "http://a/1.m3u8" in row_f10["failed_urls"], row_f10["failed_urls"])
check("换源结果标记 stalled", result.get("stalled") is True, result)
check("换源后进度复位", row_f10["progress"] == 0.0, row_f10["progress"])

# F11 无候选可换 → 有界终态 failed（绝不无限重搜）
qf11, sf11, cf11 = make_watchdog(timeout_minutes=10, seconds_idle=99999,
                                 alts=(), tid="tnone")
qf11.reap_stalled_tasks()
task_f11 = qf11._read()[0]
qf11._persist_terminal_intent = lambda intent: None  # 桩掉落盘，只验证不换源
res11 = qf11._requeue_with_fallback(task_f11, "下载无进展超过 10 分钟")
check("卡住且无候选时换源返回 False（有界，终态 failed）", res11 is False, res11)
check("无候选时不产生新 url", task_f11.url == "http://a/1.m3u8", task_f11.url)

print()
print("=" * 72)
print(f"结果：通过 {PASS} / 失败 {FAIL}")
print("=" * 72)
sys.exit(1 if FAIL else 0)
