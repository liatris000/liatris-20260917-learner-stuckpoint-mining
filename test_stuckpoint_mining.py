from types import SimpleNamespace

from stuckpoint_mining import StuckpointRecord, aggregate, extract_stuckpoint


class FakeToolUseBlock:
    def __init__(self, name: str, input_: dict):
        self.type = "tool_use"
        self.name = name
        self.input = input_


class FakeMessages:
    def __init__(self, tool_name: str, payload: dict):
        self._tool_name = tool_name
        self._payload = payload
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[FakeToolUseBlock(self._tool_name, self._payload)])


class FakeClient:
    def __init__(self, tool_name: str, payload: dict):
        self.messages = FakeMessages(tool_name, payload)


def test_extract_stuckpoint_parses_structured_output():
    payload = {
        "unit": "一次関数",
        "category": "calculation_slip",
        "confidence": 0.85,
        "evidence": "yの増加量とxの増加量を逆に割ってしまいました",
    }
    client = FakeClient("submit_stuckpoint", payload)

    result = extract_stuckpoint(
        client,
        unit_hint="一次関数",
        correct=False,
        comment="グラフの傾きを求める問題で、yの増加量とxの増加量を逆に割ってしまいました。",
    )

    assert isinstance(result, StuckpointRecord)
    assert result.category == "calculation_slip"
    assert result.confidence == 0.85
    # tool_choice で強制していることを確認(自由テキスト応答に倒れないため)
    assert client.messages.last_kwargs["tool_choice"] == {"type": "tool", "name": "submit_stuckpoint"}


def test_aggregate_counts_by_unit_and_category():
    results = [
        {"stuckpoint": StuckpointRecord(unit="一次関数", category="concept_gap", confidence=0.6, evidence="a")},
        {"stuckpoint": StuckpointRecord(unit="一次関数", category="concept_gap", confidence=0.7, evidence="b")},
        {"stuckpoint": StuckpointRecord(unit="分数の計算", category="calculation_slip", confidence=0.9, evidence="c")},
    ]

    agg = aggregate(results)

    assert agg["一次関数"]["concept_gap"] == 2
    assert agg["分数の計算"]["calculation_slip"] == 1


def test_extract_stuckpoint_raises_when_tool_not_used():
    class NoToolMessages:
        def create(self, **kwargs):
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="自由記述で返してしまった")])

    client = SimpleNamespace(messages=NoToolMessages())

    try:
        extract_stuckpoint(client, unit_hint="確率の基礎", correct=False, comment="わかりません")
    except RuntimeError as e:
        assert "tool_use" in str(e)
    else:
        raise AssertionError("RuntimeError が送出されるべき")
