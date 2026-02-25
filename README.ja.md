# Backlog Wiki Sync

Backlog Wikiとローカル環境を同期するコマンドラインツール

**ダウンロード → ローカルで編集 → アップロード** のワークフローを実現します。

## 概要

このパッケージは3つのコマンドを提供します：

- **backlog-wiki-downloader**: Backlog WikiをMarkdown形式でダウンロード
- **backlog-wiki-uploader**: 編集したページをBacklogにアップロード
- **github-wiki-builder**: ダウンロードしたWikiをGitHub Wiki形式に変換

![](images/001.png)

## 機能

### ダウンローダー
- 指定プロジェクトの全Wikiページを一括ダウンロード
- 特定の階層のみをフィルタしてダウンロード可能
- Wikiの階層構造を維持してフォルダを作成
- 添付ファイル（画像など）を自動ダウンロード
- Backlog記法をMarkdown形式に変換
- 各フォルダに`index.md`（内容）と`memo.md`（BacklogのURLとページ名）を作成

### アップローダー
- ローカルのWikiページをBacklogにアップロード
- 添付ファイル（画像など）もアップロード（Backlogに存在しないもののみ）
- `memo.md`から対応するBacklog Wikiページを特定
- Markdown記法をBacklog記法に変換
- URLで特定ページを指定、または全ページを一括アップロード
- ドライランモードで変更をプレビュー可能

### GitHub Wiki Builder
- ダウンロードしたWikiフォルダをGitHub Wiki形式に変換
- 折りたたみ可能なナビゲーション付き`_Sidebar.md`を自動生成（HTML `<details>`タグ使用）
- ページと画像を安全なASCIIファイル名でコピー
- パス区切り文字を設定可能（デフォルト: ` › `）
- サイドバーの展開レベルを設定可能（デフォルト: 2階層）
- 重複するh1タイトルを削除（GitHub Wikiはファイル名をタイトルとして表示するため）

## インストール

### pipを使用

```bash
git clone https://github.com/furuya02/backlog-wiki-sync.git
cd backlog-wiki-sync
pip install -e .
```

pipでインストール後、すべてのコマンドがグローバルに使用可能になります：

```bash
backlog-wiki-downloader
backlog-wiki-uploader
github-wiki-builder
```

## 設定ファイル

カレントディレクトリに `.backlog-wiki-sync.json` ファイルを作成すると、毎回認証情報を入力する必要がなくなります。

```json
{
  "space_url": "https://xxx.backlog.com",
  "project_key": "MYPRJ",
  "api_key": "YOUR_API_KEY",
  "wiki_prefix": "",
  "output_dir": "Wiki"
}
```

設定ファイルが存在する場合、ツールは自動的に値を読み込みます。コマンドライン引数は設定ファイルの値より優先されます。

> **注意**: 設定ファイルにはAPIキーが含まれます。誤ってコミットされないよう、`.gitignore`に自動的に追加されています。

### GitHub Wiki Builder設定

`.github-wiki-builder.json`ファイルを作成できます：

```json
{
  "wiki_path": "./Wiki",
  "output_path": "./github-wiki"
}
```

## 使用方法（ダウンローダー）

### 対話モード（推奨）

```bash
backlog-wiki-downloader
```

プロンプトに従って以下を入力：
1. BacklogスペースURL（例: `https://xxx.backlog.com`）
2. プロジェクトキー（例: `MY_PRJ`）
3. APIキー（入力時は表示されません）
4. Wiki階層フィルタ（例: `開発/設計書`、空欄で全Wiki対象）

### コマンドライン引数モード

```bash
backlog-wiki-downloader \
  --url https://xxx.backlog.com \
  --project MY_PRJ \
  --api-key YOUR_API_KEY
```

### 特定の階層のみダウンロード

```bash
backlog-wiki-downloader \
  --url https://xxx.backlog.com \
  --project MY_PRJ \
  --api-key YOUR_API_KEY \
  --prefix "開発/設計書"
```

### オプション

```
usage: backlog-wiki-downloader [-h] [-u URL] [-p PROJECT] [-k API_KEY] [-f PREFIX] [-o OUTPUT]

BacklogプロジェクトからWikiページをダウンロード

options:
  -h, --help            ヘルプメッセージを表示して終了
  -u URL, --url URL     BacklogスペースURL
  -p PROJECT, --project PROJECT
                        プロジェクトキー
  -k API_KEY, --api-key API_KEY
                        Backlog APIキー
  -f PREFIX, --prefix PREFIX
                        Wiki階層フィルタ（デフォルト: 全Wiki）
  -o OUTPUT, --output OUTPUT
                        出力ディレクトリ（デフォルト: Wiki）
```

## 使用方法（アップローダー）

### 対話モード（推奨）

```bash
backlog-wiki-uploader
```

プロンプトに従って以下を入力：
1. APIキー（入力時は表示されません）
2. アップロードするWikiのURL（空欄で全Wiki対象）
3. BacklogスペースURL（Wiki URLが空欄の場合のみ）

### コマンドライン引数モード

特定のWikiページをアップロード：

```bash
backlog-wiki-uploader \
  --api-key YOUR_API_KEY \
  --target-url "https://xxx.backlog.com/alias/wiki/12345"
```

### ドライランモード（実際にはアップロードしない）

```bash
backlog-wiki-uploader \
  --api-key YOUR_API_KEY \
  --target-url "https://xxx.backlog.com/alias/wiki/12345" \
  --dry-run
```

### オプション

```
usage: backlog-wiki-uploader [-h] [-k API_KEY] [-t TARGET_URL] [-n]

ローカルのWikiページをBacklogにアップロード（上書き）

options:
  -h, --help            ヘルプメッセージを表示して終了
  -k API_KEY, --api-key API_KEY
                        Backlog APIキー
  -t TARGET_URL, --target-url TARGET_URL
                        対象WikiのURL（例: https://xxx.backlog.com/alias/wiki/12345）
  -n, --dry-run         ドライランモード（実際にはアップロードしない）
```

## 使用方法（GitHub Wiki Builder）

### 事前準備

まずGitHub Wikiリポジトリをクローンします：

```bash
git clone git@github.com:<org>/<repo>.wiki.git ./github-wiki
```

### 対話モード（推奨）

```bash
github-wiki-builder
```

プロンプトに従って以下を入力：
1. Wikiフォルダのパス（デフォルト: `./Wiki`）
2. GitHub Wikiリポジトリのパス（例: `./github-wiki`）

### コマンドライン引数モード

```bash
github-wiki-builder \
  --input ./Wiki \
  --output ./github-wiki
```

### オプション

```
usage: github-wiki-builder [-h] [-i INPUT] [-o OUTPUT] [-s SEPARATOR] [-e EXPAND_LEVEL]

Backlog WikiをGitHub Wiki形式に変換

options:
  -h, --help            ヘルプメッセージを表示して終了
  -i INPUT, --input INPUT
                        Wikiフォルダのパス（デフォルト: ./Wiki）
  -o OUTPUT, --output OUTPUT
                        GitHub Wikiリポジトリのパス
  -s SEPARATOR, --separator SEPARATOR
                        パス区切り文字（デフォルト: ' › '）
  -e EXPAND_LEVEL, --expand-level EXPAND_LEVEL
                        サイドバーの展開レベル（デフォルト: 2）
```

### 実行後

変更をGitHubにプッシュします：

```bash
cd ./github-wiki
git add .
git commit -m "Update Wiki"
git push origin master
```

## 出力形式

### ダウンローダーの出力（Wikiフォルダ）

```
Wiki/
├── ページ名1/
│   ├── index.md      # Wikiの内容（Markdown形式）
│   ├── memo.md       # BacklogのURLとページ名
│   └── *.png         # 添付画像
├── 親ページ/
│   ├── index.md
│   ├── memo.md
│   └── 子ページ/
│       ├── index.md
│       ├── memo.md
│       └── *.png
```

### GitHub Wiki Builderの出力

```
github-wiki/
├── _Sidebar.md                    # ナビゲーションサイドバー（自動生成）
├── Home.md                        # GitHub Wikiホームページ（手動作成）
├── ページ名1.md                   # Wikiページ
├── 親ページ › 子ページ.md         # ネストされたページ（ファイル名に区切り文字）
├── img_xxxxxxxx_001.png           # 画像（安全なASCIIファイル名）
└── img_yyyyyyyy_002.png
```

## プロジェクトキーの確認方法

プロジェクトキーは、Backlogプロジェクトを識別する英数字の文字列です。

### 方法1: URLから確認

プロジェクトのページを開くと、URLに含まれています。

```
https://xxx.backlog.com/projects/MY_PRJ
                                 ^^^^^^
                                 これがプロジェクトキー
```

### 方法2: プロジェクト設定から確認

1. 対象プロジェクトを開く
2. 左メニュー → **プロジェクト設定**
3. **基本設定** タブ
4. 「プロジェクトキー」欄に表示

## APIキーの取得方法

1. Backlogにログイン
2. 右上のアイコン → **個人設定**
3. **API** → **新しいAPIキーを発行**
4. メモを入力（例: `Wiki Downloader`）して発行
5. 表示されたAPIキーをコピー（一度しか表示されません）

> **注意**: APIキーは第三者に漏らさないでください。漏洩した場合は、同じ画面から削除して再発行できます。

## 変換ルール

### フォルダ名・ファイル名

- 空白 → `_`（アンダースコア）
- `/` → サブフォルダとして分割
- 画像ファイル名の空白も`_`に変換

### Backlog記法 ↔ Markdown

| Backlog記法 | Markdown |
|------------|----------|
| `![image][filename.png]` | `![image](filename.png)` |
| `*` 箇条書き | `-` 箇条書き |
| テーブル、コードブロック | そのまま維持 |

## 注意事項

- 大量のWikiページがある場合、処理に時間がかかります
- ダウンロード時、すでに`index.md`が存在するフォルダはスキップされます
- アップロード時、Backlogの既存ページを上書きします
- 添付ファイル（画像）はBacklogに存在しないもののみアップロードされます
- APIキーは履歴に残らないよう、対話モードの使用を推奨します

## 必要要件

- Python 3.10以上
- Backlog APIキー

## ライセンス

MIT License

## コントリビューション

コントリビューションは歓迎します！お気軽にPull Requestを送ってください。
