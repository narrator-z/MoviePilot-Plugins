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
import types

PKG = "luna_src"
SRC = os.environ.get("LUNA_SRC") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
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
print(f"结果：通过 {PASS} / 失败 {FAIL}")
print("=" * 72)
sys.exit(1 if FAIL else 0)
