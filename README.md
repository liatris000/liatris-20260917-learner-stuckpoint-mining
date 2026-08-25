# 学習ログ つまずき構造化検出

学習ログ(小テストの正誤 + 自由記述コメント)を Claude API の構造化出力(tool use)でパースし、
「単元 x つまずき種別」の集計と静的 HTML レポートを出力するスクリプト。

入力データはすべて合成データです。実在の個人・団体・学習履歴とは関係ありません。

## セットアップ

```bash
pip install -r requirements.txt
```

## 使い方

Claude API キーがある場合:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 stuckpoint_mining.py --input sample_logs.json --output index.html
```

API キーが無くても、モック応答でレポート生成の動作だけ確認できます(`index.html` はこのモードで生成したものです):

```bash
python3 stuckpoint_mining.py --input sample_logs.json --output index.html --demo
```

## テスト

`anthropic.Anthropic` クライアントをモックし、tool 定義の組み立てと `tool_use` ブロックのパース経路だけを確認します(モデルの生成品質そのものはテスト対象外)。

```bash
python3 -m pytest test_stuckpoint_mining.py -v
```

## ファイル構成

- `stuckpoint_mining.py` — 抽出・集計・レポート生成のメインロジック
- `test_stuckpoint_mining.py` — モックを使ったユニットテスト
- `sample_logs.json` — 合成の学習ログサンプル(12件)
- `index.html` — `--demo` モードで生成したサンプルレポート(GitHub Pages で公開)
