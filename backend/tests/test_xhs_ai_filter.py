from app.services.xhs_ai_filter import cluster_is_ai_related, is_ai_related


def test_obvious_ai_chinese():
    assert is_ai_related("大模型")
    assert is_ai_related("智能体")
    assert is_ai_related("提示词工程")
    assert is_ai_related("AI 编程实战")


def test_obvious_ai_short_english():
    assert is_ai_related("GPT")
    assert is_ai_related("agent")
    assert is_ai_related("MCP")
    assert is_ai_related("Claude")
    assert is_ai_related("Codex")


def test_obvious_non_ai():
    assert not is_ai_related("二次元")
    assert not is_ai_related("好视频扶持计划")
    assert not is_ai_related("穿搭")
    assert not is_ai_related("美食探店")


def test_non_ai_topic_even_with_ai_tag():
    # 主体是非 AI 主题，蹭 AI 标签也剔除
    assert not is_ai_related("二次元穿搭 AI")


def test_short_english_word_boundary():
    # "AI" 命中，但 "air"/"Brain" 不应误中
    assert is_ai_related("AI")
    assert not is_ai_related("air")
    assert not is_ai_related("Brain")
    assert not is_ai_related("hair")


def test_no_signal_defaults_non_ai():
    # 既无强 AI 信号也无明确非 AI 词，保守判非 AI
    assert not is_ai_related("日常记录")
    assert not is_ai_related("")


def test_cluster_is_ai_related_fallback():
    # 簇内任一标题/标签沾 AI 即保留
    assert cluster_is_ai_related(["日常记录", "GPT 使用心得"])
    assert not cluster_is_ai_related(["二次元", "穿搭分享"])
    assert not cluster_is_ai_related([])
