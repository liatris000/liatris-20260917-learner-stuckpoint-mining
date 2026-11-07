# 学習ログ つまずき構造化検出

学習ログ(小テストの正誤 + 自由記述コメント)を Claude API の構造化出力(tool use)でパースし、「単元 x つまずき種別」の集計と静的 HTML レポートを出力するスクリプト。

記事: https://zenn.dev/liatris/articles/20260917-learner-stuckpoint-mining

入力データはすべて合成データ。実在の個人・団体・学習履歴とは関係ない。

## 前提

- Python 3(3.14.6 で確認。これより古い版は試していない)
- `requirements.txt` の依存(`anthropic` / `pydantic` / `pytest`)
- 実際のモデルで抽出するには Anthropic の API キー。`--demo` とテストはキーなしで動く

## 動かし方

```bash
git clone https://github.com/liatris000/liatris-20260917-learner-stuckpoint-mining.git
cd liatris-20260917-learner-stuckpoint-mining
pip install -r requirements.txt

# API キーなし: 固定ルールのモック応答でレポートを作る
python3 stuckpoint_mining.py --input sample_logs.json --output index.html --demo

# テスト(API キー不要)
python3 -m pytest test_stuckpoint_mining.py -v

# API キーあり: 実際のモデルで抽出する
export ANTHROPIC_API_KEY=sk-ant-...
python3 stuckpoint_mining.py --input sample_logs.json --output index.html
```

## 期待される出力

`--demo`:

```text
✅ index.html に 12 件のレポートを出力しました
```

リポジトリの `index.html` は、このモードで作ったもの(GitHub Pages: https://liatris000.github.io/liatris-20260917-learner-stuckpoint-mining/ )。

テスト:

```text
test_stuckpoint_mining.py::test_extract_stuckpoint_parses_structured_output PASSED [ 33%]
test_stuckpoint_mining.py::test_aggregate_counts_by_unit_and_category PASSED [ 66%]
test_stuckpoint_mining.py::test_extract_stuckpoint_raises_when_tool_not_used PASSED [100%]
============================== 3 passed ==============================
```

## 確かめていない範囲

- 実際のモデルで抽出した結果は、リポジトリに置いていない。`index.html` はモック応答で作ったもの
- 分類(5 種のつまずき種別)が実データに対して当たるかは検証していない
- テストで確かめているのは、tool 定義の組み立てと `tool_use` のパース経路まで

## ファイル構成

- `stuckpoint_mining.py` — 抽出・集計・レポート生成のメインロジック
- `test_stuckpoint_mining.py` — モックを使ったユニットテスト
- `sample_logs.json` — 合成の学習ログサンプル(12 件)
- `index.html` — `--demo` モードで生成したサンプルレポート

## 記事

https://zenn.dev/liatris/articles/20260917-learner-stuckpoint-mining

## ライセンス

MIT
