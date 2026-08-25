"""学習ログ(小テスト結果 + 自由記述コメント)を Claude API の構造化出力でパースし、
つまずきパターンを検出・集計して静的 HTML レポートを出力する。

使い方:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 stuckpoint_mining.py --input sample_logs.json --output report.html

API キーが無い場合は --demo を付けるとモック応答でレポート生成のみ確認できる。
"""
from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

MODEL = "claude-sonnet-5"

CATEGORY_LABELS = {
    "concept_gap": "概念理解の不足",
    "calculation_slip": "計算・手順のミス",
    "misread_instruction": "問題文の読み違い",
    "time_pressure": "時間切れ・見直し不足",
    "other": "その他",
}


class StuckpointRecord(BaseModel):
    unit: str = Field(description="つまずきが起きている単元名(ログのunit_hintを踏まえて正規化する)")
    category: str = Field(
        description=(
            "つまずきの種別。次のいずれか1つ: "
            "concept_gap(概念理解の不足) / calculation_slip(計算・手順のミス) / "
            "misread_instruction(問題文の読み違い) / time_pressure(時間切れ・見直し不足) / other(その他)"
        )
    )
    confidence: float = Field(description="分類の確信度(0.0〜1.0)")
    evidence: str = Field(description="分類根拠として引用したコメント中の一節(短く)")


def _model_to_tool(model: type[BaseModel], name: str, description: str) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return {"name": name, "description": description, "input_schema": schema}


def _call_structured(client: Any, *, system: str, user: str, tool: dict[str, Any]) -> dict[str, Any]:
    """構造化出力を1つの tool_use ブロックとして強制取得する共通処理。"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user}],
    )
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
            return block.input
    raise RuntimeError("tool_use ブロックが返らなかった(モデル or プロンプトを確認)")


def extract_stuckpoint(client: Any, *, unit_hint: str, correct: bool, comment: str) -> StuckpointRecord:
    tool = _model_to_tool(
        StuckpointRecord,
        "submit_stuckpoint",
        "学習ログ1件分のつまずき分類を提出する",
    )
    user = (
        f"単元(自己申告): {unit_hint}\n"
        f"正誤: {'正解' if correct else '不正解'}\n"
        f"生徒コメント: {comment}\n"
        "上記の小テスト結果とコメントから、つまずきの種別を1つ分類して。"
        "正解した場合でも、コメントから軽微なつまずきが読み取れるなら記録すること。"
    )
    data = _call_structured(
        client,
        system=(
            "あなたは学習ログを分析するアシスタントです。"
            "生徒の自由記述コメントから、つまずきの種別・該当単元・確信度を構造化して抽出します。"
            "断定できない場合は confidence を低めにしてください。"
        ),
        user=user,
        tool=tool,
    )
    return StuckpointRecord.model_validate(data)


def load_logs(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def mine_logs(client: Any, logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for entry in logs:
        record = extract_stuckpoint(
            client,
            unit_hint=entry["unit_hint"],
            correct=entry["correct"],
            comment=entry["comment"],
        )
        results.append({**entry, "stuckpoint": record})
    return results


def aggregate(results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """単元 x 種別 の件数を集計する。"""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        record: StuckpointRecord = r["stuckpoint"]
        counts[record.unit][record.category] += 1
    return {unit: dict(cats) for unit, cats in counts.items()}


def _bar(count: int, max_count: int, width_px: int = 220) -> str:
    if max_count <= 0:
        width = 0
    else:
        width = max(4, int(width_px * count / max_count))
    return f'<span class="bar" style="width:{width}px"></span>'


def render_html(results: list[dict[str, Any]], agg: dict[str, dict[str, int]]) -> str:
    max_count = max((c for cats in agg.values() for c in cats.values()), default=1)

    rows_agg = []
    for unit in sorted(agg, key=lambda u: -sum(agg[u].values())):
        for category, count in sorted(agg[unit].items(), key=lambda kv: -kv[1]):
            label = CATEGORY_LABELS.get(category, category)
            rows_agg.append(
                f"<tr><td>{html.escape(unit)}</td><td>{html.escape(label)}</td>"
                f"<td class=\"count-cell\">{_bar(count, max_count)} {count}</td></tr>"
            )

    rows_detail = []
    for r in results:
        record: StuckpointRecord = r["stuckpoint"]
        label = CATEGORY_LABELS.get(record.category, record.category)
        rows_detail.append(
            "<tr>"
            f"<td>{html.escape(r['log_id'])}</td>"
            f"<td>{html.escape(record.unit)}</td>"
            f"<td>{html.escape(label)}</td>"
            f"<td>{record.confidence:.2f}</td>"
            f"<td>{html.escape(record.evidence)}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>学習ログ つまずき検出レポート</title>
<style>
  body {{ font-family: -apple-system, "Hiragino Sans", sans-serif; margin: 2rem auto; max-width: 800px; color: #222; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
  th, td {{ border-bottom: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }}
  th {{ background: #f5f5f5; }}
  .bar {{ display: inline-block; height: 10px; background: #6b8afd; vertical-align: middle; margin-right: 6px; border-radius: 2px; }}
  .count-cell {{ white-space: nowrap; }}
  .note {{ color: #666; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>学習ログ つまずき検出レポート</h1>
<p class="note">入力: {len(results)}件のログ(小テスト結果 + 自由記述コメント、合成データ)</p>

<h2>単元 x つまずき種別 集計</h2>
<table>
<tr><th>単元</th><th>つまずき種別</th><th>件数</th></tr>
{''.join(rows_agg)}
</table>

<h2>ログ別 詳細</h2>
<table>
<tr><th>log_id</th><th>単元</th><th>種別</th><th>確信度</th><th>根拠</th></tr>
{''.join(rows_detail)}
</table>
</body>
</html>
"""


def _demo_client() -> Any:
    """API キー無しでも動作確認できるよう、固定の分類ロジックでモック応答を返すクライアント。"""
    from types import SimpleNamespace

    def _classify(comment: str, correct: bool) -> tuple[str, float, str]:
        c = comment
        if any(k in c for k in ["読み違", "読み飛ば", "取り違え", "意味を取り違"]):
            return "misread_instruction", 0.8, c[:20]
        if any(k in c for k in ["時間", "見直し", "時間切れ"]):
            return "time_pressure", 0.75, c[:20]
        if any(k in c for k in ["意味", "自信が持てません", "曖昧", "腑に落ち"]):
            return "concept_gap", 0.7, c[:20]
        if any(k in c for k in ["逆に", "書き間違え", "約分を忘れ", "数え間違え", "数え漏れ"]):
            return "calculation_slip", 0.85, c[:20]
        return ("other", 0.5, c[:20]) if not correct else ("concept_gap", 0.4, c[:20])

    class _FakeMessages:
        def create(self, **kwargs):
            user_text = kwargs["messages"][0]["content"]
            unit_hint = user_text.split("単元(自己申告): ", 1)[1].split("\n", 1)[0]
            correct = "正解" in user_text.split("正誤: ", 1)[1].split("\n", 1)[0]
            comment = user_text.split("生徒コメント: ", 1)[1].split("\n", 1)[0]
            category, confidence, evidence = _classify(comment, correct)
            payload = {
                "unit": unit_hint,
                "category": category,
                "confidence": confidence,
                "evidence": evidence,
            }
            block = SimpleNamespace(type="tool_use", name="submit_stuckpoint", input=payload)
            return SimpleNamespace(content=[block])

    return SimpleNamespace(messages=_FakeMessages())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("sample_logs.json"))
    parser.add_argument("--output", type=Path, default=Path("report.html"))
    parser.add_argument("--demo", action="store_true", help="APIキー無しでモック応答を使う")
    args = parser.parse_args()

    logs = load_logs(args.input)

    if args.demo:
        client = _demo_client()
    else:
        import anthropic

        client = anthropic.Anthropic()

    results = mine_logs(client, logs)
    agg = aggregate(results)
    args.output.write_text(render_html(results, agg), encoding="utf-8")
    print(f"✅ {args.output} に {len(results)} 件のレポートを出力しました")


if __name__ == "__main__":
    main()
