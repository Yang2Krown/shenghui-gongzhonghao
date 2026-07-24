from datetime import datetime, timedelta

from risk import (
    COOLDOWN_CAP_MINUTES,
    COOLDOWN_FLOOR_MINUTES,
    COOLDOWN_UNTIL_KEY,
    RECOVERY_SUCCESS_THRESHOLD,
    RiskBackoff,
)
from storage import LocalStore


def make_backoff(tmp_path):
    store = LocalStore(tmp_path / "agent.sqlite3")
    return RiskBackoff(store), store


def resume_delta_minutes(store):
    resume_at = datetime.fromisoformat(store.get(COOLDOWN_UNTIL_KEY))
    return (resume_at - datetime.now()).total_seconds() / 60


def test_first_block_matches_legacy_range(tmp_path):
    backoff, store = make_backoff(tmp_path)
    backoff.on_block()
    # 首次触发落在 [8,12] 分钟（10 ± 20%），与旧 RISK_COOLDOWN_MINUTES=(8,12) 等价。
    assert 7.9 <= resume_delta_minutes(store) <= 12.1


def test_exponential_backoff_on_repeat(tmp_path):
    backoff, store = make_backoff(tmp_path)
    base = []
    for _ in range(3):
        backoff.on_block()
        base.append(backoff.current_cooldown_minutes())
        store.set(COOLDOWN_UNTIL_KEY, None)  # 清掉冷却，模拟连续触发
    assert base[0] == COOLDOWN_FLOOR_MINUTES
    assert base[1] == COOLDOWN_FLOOR_MINUTES * 2
    assert base[2] == COOLDOWN_FLOOR_MINUTES * 4  # floor × 2^(blocks-1)：10→20→40


def test_backoff_caps_at_max(tmp_path):
    backoff, store = make_backoff(tmp_path)
    for _ in range(10):
        backoff.on_block()
        store.set(COOLDOWN_UNTIL_KEY, None)
    assert backoff.current_cooldown_minutes() == COOLDOWN_CAP_MINUTES


def test_recovers_on_success(tmp_path):
    backoff, store = make_backoff(tmp_path)
    backoff.on_block()
    store.set(COOLDOWN_UNTIL_KEY, None)
    backoff.on_block()
    store.set(COOLDOWN_UNTIL_KEY, None)
    before = backoff.current_cooldown_minutes()
    for _ in range(RECOVERY_SUCCESS_THRESHOLD):
        backoff.on_success()
    assert backoff.current_cooldown_minutes() < before


def test_manual_verify_resets(tmp_path):
    backoff, store = make_backoff(tmp_path)
    for _ in range(4):
        backoff.on_block()
        store.set(COOLDOWN_UNTIL_KEY, None)
    backoff.on_manual_verify()
    assert backoff.current_cooldown_minutes() == COOLDOWN_FLOOR_MINUTES
    state = store.get("risk_state")
    assert state["consecutive_blocks"] == 0


def test_on_block_idempotent_during_cooldown(tmp_path):
    backoff, store = make_backoff(tmp_path)
    backoff.on_block()
    blocks_after_first = store.get("risk_state")["consecutive_blocks"]
    # 冷却未过期时重复 on_block 不累加计数（防止 verify_session 探测把指数打飞）。
    backoff.on_block()
    backoff.on_block()
    assert store.get("risk_state")["consecutive_blocks"] == blocks_after_first


def test_backoff_persists_across_restart(tmp_path):
    backoff, store = make_backoff(tmp_path)
    for _ in range(3):
        backoff.on_block()
        store.set(COOLDOWN_UNTIL_KEY, None)
    expected = backoff.current_cooldown_minutes()
    # 新建实例（模拟重启）后冷却基数保持。
    assert RiskBackoff(store).current_cooldown_minutes() == expected


def test_future_cooldown_until_is_respected(tmp_path):
    backoff, store = make_backoff(tmp_path)
    future = (datetime.now() + timedelta(minutes=33)).isoformat(timespec="minutes")
    store.set(COOLDOWN_UNTIL_KEY, future)
    resume_at = backoff.on_block()
    # 已存在的未来恢复时间被原样返回，不被重算。
    assert resume_at == datetime.fromisoformat(future)
