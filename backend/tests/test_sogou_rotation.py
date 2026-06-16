"""搜狗案例源关键词轮转窗口的自检（纯逻辑，不依赖 DB / 网络）。

复刻 sogou_wechat_adapter 里的取窗逻辑：每个时间片取 rb 个、环形绕回，
连续若干片应覆盖全部关键词、且每片大小恒为 rb。
"""


def _window(keywords, rb, slot):
    n = len(keywords)
    start = (slot * rb) % n
    return (keywords + keywords)[start:start + rb]


def test_full_coverage_and_wrap():
    kw = [f"号{i}" for i in range(29)]
    rb = 4
    seen = set()
    sizes = set()
    # 跑够一轮多一点：ceil(29/4)=8 片
    for slot in range(8):
        w = _window(kw, rb, slot)
        sizes.add(len(w))
        seen.update(w)
    assert sizes == {rb}, f"每片大小应恒为 {rb}，实际 {sizes}"
    assert seen == set(kw), f"一轮应覆盖全部 29 个，漏了 {set(kw) - seen}"


def test_wrap_at_boundary():
    kw = [f"号{i}" for i in range(29)]
    # slot=7 → start=28，窗口跨界：号28 + 号0,1,2
    assert _window(kw, 4, 7) == ["号28", "号0", "号1", "号2"]


if __name__ == "__main__":
    test_full_coverage_and_wrap()
    test_wrap_at_boundary()
    print("ok")
