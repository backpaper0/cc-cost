# cc-cost

Claude Code のセッションログ(`$HOME/.claude/projects/`)を集計し、モデル単価と為替レートから利用コスト(USD/JPY)を算出して表示するCLIツール。

## 特徴

- `$HOME/.claude/projects/` 配下のセッションログ(JSONL)をスキャンし、本日・今月・先月・先々月の4期間でコストを集計
- サブエージェント呼び出しなどの「サイドチェーン」(`isSidechain: true`)呼び出しも実際に課金される呼び出しとして集計に含める
- モデル単価・為替レートは設定ファイル(`config.toml`)で管理し、外部APIには問い合わせない
- 正規表現によるプロジェクトのグルーピング表示に対応
- 単価テーブルに未登録のモデルは「不明」として扱いつつ、使用量自体は集計に含める

## インストール

```bash
uv tool install .
```

もしくは開発用に editable install する場合:

```bash
uv sync
```

`pyproject.toml` の `[project.scripts]` により `cc-cost` コマンドが利用可能になります。

## 使い方

```bash
cc-cost
```

初回実行時、`~/.config/cc-cost/config.toml` が存在しなければデフォルト値で自動生成されます。

### オプション

| オプション | 説明 |
| --- | --- |
| `--config PATH` | 設定ファイルのパスを指定する(デフォルト: `~/.config/cc-cost/config.toml`) |
| `--verbose` | モデル別のトークン内訳(入力/出力/キャッシュ書込/キャッシュ読込)を表示する |
| `--no-color` | 色付き出力を無効化する(`NO_COLOR` 環境変数でも同様に無効化可能) |
| `--version` | バージョンを表示して終了する |

## 設定ファイル (`config.toml`)

`~/.config/cc-cost/config.toml` に以下の内容を記述します。

```toml
[exchange_rate]
# USD -> JPY 換算レート
usd_to_jpy = 150.0

# $HOME/.claude/projects/ 配下のディレクトリ名にマッチする正規表現(Pythonのre.searchで判定)。
# 定義した順に評価し、最初にマッチしたグループに割り当てる。
# name 側では \1 のようにキャプチャグループを参照できる。
# どのパターンにもマッチしないプロジェクトは、ディレクトリ名を読みやすいパス形式
# (先頭の "-" を "/" に変換したもの)に変換した名前がそのままグループ名になる。
#
# 例:
# [[project_groups]]
# pattern = "^-home-dev-workspace-cc-cost$"
# name = "cc-cost"

# モデルごとの単価(USD / 1,000,000 トークン)
[models.claude-sonnet-5]
input = 2.00
output = 10.00
cache_write_5m = 2.50
cache_write_1h = 4.00
cache_read = 0.20
```

単価・為替レートは動的取得せず、この設定ファイルの値をそのまま使用します。単価改定や為替変動があった場合は、ユーザー自身が値を書き換えてください。更新すると、先月・先々月など過去期間の表示金額も新しい値で再計算されます(詳細: [docs/adr/0003](docs/adr/0003-apply-current-rates-to-all-periods.md))。

## 用語

セッション、ログエントリ、API呼び出し、使用量、サイドチェーンなどの用語の定義は [CONTEXT.md](CONTEXT.md) を参照してください。

## 開発

- Python >= 3.11 / 依存パッケージなし
- ビルドバックエンド: hatchling
- 詳細な設計判断は [docs/adr/](docs/adr/) の各ADRを参照
