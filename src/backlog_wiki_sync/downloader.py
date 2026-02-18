#!/usr/bin/env python3
"""
Backlog Wiki Downloader

Backlogプロジェクトの全WikiページをMarkdown形式でダウンロードするツール

使用方法:
    backlog-wiki-downloader

機能:
    - 指定プロジェクトの全Wikiページを取得
    - 階層構造でフォルダを作成
    - 各ページの内容と添付ファイルをダウンロード
    - Backlog記法をMarkdownに変換して保存
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from getpass import getpass
from urllib.parse import urlparse


class BacklogWikiDownloader:
    """Backlog Wikiダウンローダー"""

    def __init__(
        self,
        space_url: str,
        api_key: str,
        project_key: str,
        wiki_prefix: str = "",
        output_dir: str = "Wiki",
    ):
        """
        初期化

        Args:
            space_url: BacklogスペースURL (例: https://xxx.backlog.com)
            api_key: Backlog APIキー
            project_key: プロジェクトキー
            wiki_prefix: Wikiの階層フィルタ (例: "開発/設計書")
            output_dir: 出力ディレクトリ (デフォルト: "Wiki")
        """
        self.space_url = self._extract_base_url(space_url)
        self.api_key = api_key
        self.project_key = project_key
        self.wiki_prefix = wiki_prefix.strip("/") if wiki_prefix else ""
        self.output_dir = Path(output_dir)

    @staticmethod
    def _extract_base_url(url: str) -> str:
        """URLからベースURL（スキーム + ホスト）を抽出

        例: https://xxx.backlog.com/wiki/EX -> https://xxx.backlog.com
        """
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        # スキームがない場合はhttpsを付けて再解析
        if not parsed.scheme:
            parsed = urlparse(f"https://{url}")
            return f"{parsed.scheme}://{parsed.netloc}"
        return url.rstrip("/")

    def _api_get(self, endpoint: str) -> Optional[dict | list]:
        """API GETリクエスト"""
        url = f"{self.space_url}/api/v2/{endpoint}"
        separator = "&" if "?" in endpoint else "?"
        url = f"{url}{separator}apiKey={self.api_key}"

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"  API Error: {e}")
            return None
        except urllib.error.URLError as e:
            print(f"  Network Error: {e}")
            return None

    def _download_file(self, url: str, target_path: Path) -> bool:
        """ファイルをダウンロード"""
        full_url = f"{url}{'&' if '?' in url else '?'}apiKey={self.api_key}"
        try:
            with urllib.request.urlopen(full_url, timeout=30) as response:
                with open(target_path, "wb") as f:
                    f.write(response.read())
            return True
        except (urllib.error.URLError, OSError) as e:
            print(f"  Download Error: {e}")
            return False

    def get_all_wikis(self) -> list:
        """プロジェクトの全Wikiページ一覧を取得"""
        print(f"Fetching wiki list for project: {self.project_key}")
        wikis = self._api_get(f"wikis?projectIdOrKey={self.project_key}")
        if wikis is None:
            return []
        print(f"Found {len(wikis)} wiki pages")
        return wikis

    def get_wiki_content(self, wiki_id: int) -> Optional[dict]:
        """Wikiページの内容を取得"""
        return self._api_get(f"wikis/{wiki_id}")

    def get_attachments(self, wiki_id: int) -> list:
        """添付ファイル一覧を取得"""
        result = self._api_get(f"wikis/{wiki_id}/attachments")
        return result if result else []

    def download_attachment(
        self, wiki_id: int, attachment_id: int, filename: str, target_dir: Path
    ) -> bool:
        """添付ファイルをダウンロード"""
        url = f"{self.space_url}/api/v2/wikis/{wiki_id}/attachments/{attachment_id}"
        target_path = target_dir / filename
        return self._download_file(url, target_path)

    @staticmethod
    def sanitize_name(name: str) -> str:
        """名前をサニタイズ（空白をアンダースコアに変換、禁止文字を除去）"""
        # 空白をアンダースコアに変換
        name = name.replace(" ", "_")
        # ファイルシステムで使えない文字を削除
        name = re.sub(r'[<>:"|?*]', "", name)
        return name

    # エイリアス（後方互換性のため）
    sanitize_folder_name = sanitize_name
    sanitize_filename = sanitize_name

    @classmethod
    def convert_backlog_to_markdown(cls, content: str) -> str:
        """Backlog記法をMarkdownに変換"""

        # 画像参照を変換: ![image][filename.png] -> ![image](filename.png)
        # また、ファイル名の空白をアンダースコアに変換
        def replace_image_ref(match: re.Match) -> str:
            alt_text = match.group(1)
            filename = cls.sanitize_filename(match.group(2))
            return f"![{alt_text}]({filename})"

        content = re.sub(r"!\[([^\]]*)\]\[([^\]]+)\]", replace_image_ref, content)

        # 箇条書きを統一（行頭の * を - に、ネストにも対応）
        # Backlog: * item, ** nested, *** deep nested
        # Markdown: - item, (indent)- nested, (indent)(indent)- deep nested
        lines = content.split("\n")
        converted_lines = []
        for line in lines:
            # ネストされた箇条書きに対応: ^(\*+)\s
            match = re.match(r"^(\*+)\s", line)
            if match:
                stars = match.group(1)
                indent = "  " * (len(stars) - 1)  # ネストレベルに応じたインデント
                line = indent + "- " + line[len(stars) + 1 :]
            converted_lines.append(line)

        return "\n".join(converted_lines)

    def process_wiki_page(self, wiki: dict) -> tuple[bool, int]:
        """
        1つのWikiページを処理

        Returns:
            tuple[bool, int]: (成功/失敗, 添付ファイル数)
                              スキップ時は (True, -1) を返す
        """
        wiki_id = wiki["id"]
        wiki_name = wiki["name"]

        # パスを解析してフォルダ構造を作成
        # 例: "開発/設計書/01 概要" -> Wiki/開発/設計書/01_概要/
        path_parts = wiki_name.split("/")
        sanitized_parts = [self.sanitize_folder_name(part) for part in path_parts]
        folder_path = self.output_dir / "/".join(sanitized_parts)

        # フォルダ作成
        folder_path.mkdir(parents=True, exist_ok=True)

        index_path = folder_path / "index.md"
        memo_path = folder_path / "memo.md"

        # すでに処理済みの場合はスキップ
        if index_path.exists():
            print(f"  Skip (already exists)")
            return (True, -1)

        # Wiki内容を取得
        wiki_data = self.get_wiki_content(wiki_id)
        if not wiki_data:
            return (False, 0)

        content = wiki_data.get("content", "")

        # memo.mdにURLとページ名を保存
        wiki_url = f"{self.space_url}/alias/wiki/{wiki_id}"
        with open(memo_path, "w", encoding="utf-8") as f:
            f.write(wiki_url + "\n")
            f.write(wiki_name + "\n")

        # 添付ファイルをダウンロード（ファイル名の空白をアンダースコアに変換）
        attachments = self.get_attachments(wiki_id)
        for att in attachments:
            att_id = att["id"]
            att_name = self.sanitize_filename(att["name"])
            att_path = folder_path / att_name
            if not att_path.exists():
                self.download_attachment(wiki_id, att_id, att_name, folder_path)

        # Backlog記法をMarkdownに変換
        markdown_content = self.convert_backlog_to_markdown(content)

        # index.mdとして保存
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        return (True, len(attachments))

    def run(self) -> None:
        """メイン処理を実行"""
        # 全Wikiページを取得
        wikis = self.get_all_wikis()
        if not wikis:
            print("No wiki pages found or API error occurred.")
            return

        # Wiki階層でフィルタリング
        if self.wiki_prefix:
            wikis = [w for w in wikis if w["name"].startswith(self.wiki_prefix)]
            print(f"Filtered by prefix '{self.wiki_prefix}': {len(wikis)} pages")
            if not wikis:
                print("No wiki pages found matching the specified prefix.")
                return

        # 名前でソート
        wikis = sorted(wikis, key=lambda x: x["name"])

        print("=" * 60)
        print(f"Downloading {len(wikis)} wiki pages to '{self.output_dir}/'")
        print("=" * 60)

        success = 0
        failed = 0

        for i, wiki in enumerate(wikis, 1):
            wiki_name = wiki["name"]
            print(f"[{i}/{len(wikis)}] {wiki_name}")

            result, attachment_count = self.process_wiki_page(wiki)
            if result:
                if attachment_count >= 0:
                    print(f"  Done ({attachment_count} attachments)")
                # スキップ時 (attachment_count == -1) はログ出力済み
                success += 1
            else:
                print(f"  Failed")
                failed += 1

        print("=" * 60)
        print(f"Completed: {success} success, {failed} failed")
        print(f"Output directory: {self.output_dir.absolute()}")


def extract_wiki_id_from_url(url: str) -> Optional[int]:
    """URLからWiki IDを抽出"""
    match = re.search(r"/alias/wiki/(\d+)", url)
    if match:
        return int(match.group(1))
    return None


def fetch_wiki_name(space_url: str, api_key: str, wiki_id: int) -> Optional[str]:
    """Wiki IDからWiki名を取得"""
    url = f"{space_url}/api/v2/wikis/{wiki_id}?apiKey={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("name")
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def resolve_wiki_prefix(user_input: str, space_url: str, api_key: str) -> str:
    """
    ユーザー入力からWiki prefixを解決

    URLが入力された場合はWiki名を取得、それ以外はそのまま返す
    """
    if not user_input:
        return ""

    # URLかどうかを判定
    wiki_id = extract_wiki_id_from_url(user_input)
    if wiki_id:
        print(f"  Fetching wiki name for ID: {wiki_id}...")
        wiki_name = fetch_wiki_name(space_url, api_key, wiki_id)
        if wiki_name:
            print(f"  Resolved to: {wiki_name}")
            return wiki_name
        else:
            print(f"  Warning: Could not fetch wiki name, using input as-is")
            return user_input

    return user_input


def get_user_input(
    default_url: str = "", default_project: str = "", default_prefix: str = ""
) -> tuple[str, str, str, str]:
    """
    ユーザーから入力を取得

    Args:
        default_url: URLのデフォルト値
        default_project: プロジェクトキーのデフォルト値
        default_prefix: Wiki階層フィルタのデフォルト値
    """
    print("=" * 60)
    print("Backlog Wiki Downloader")
    print("=" * 60)
    print()

    # スペースURLを取得
    print("BacklogスペースのURLを入力してください")
    print("例: https://xxx.backlog.com または https://xxx.backlog.jp")
    if default_url:
        print(f"デフォルト: {default_url}")
    space_url = input("URL: ").strip() or default_url

    # URLの検証と正規化
    if space_url and not space_url.startswith("http"):
        space_url = "https://" + space_url

    print()

    # プロジェクトキーを取得
    print("プロジェクトキーを入力してください")
    print("例: MYPRJ (プロジェクトURLの /projects/XXX の部分)")
    if default_project:
        print(f"デフォルト: {default_project}")
    project_key = input("Project Key: ").strip() or default_project

    print()

    # APIキーを取得
    print("APIキーを入力してください")
    print("(個人設定 → API → APIキーの発行で取得できます)")
    api_key = getpass("API Key (入力は表示されません): ").strip()

    print()

    # Wiki階層フィルタを取得
    print("取得するWikiの階層を入力してください（空欄で全Wiki対象）")
    print("例: 開発/設計書 または https://xxx.backlog.com/alias/wiki/12345")
    if default_prefix:
        print(f"デフォルト: {default_prefix}")
    prefix_input = input("Wiki Prefix or URL: ").strip() or default_prefix

    # URLが入力された場合はWiki名を取得
    wiki_prefix = resolve_wiki_prefix(prefix_input, space_url, api_key) if prefix_input else ""

    print()

    return space_url, project_key, api_key, wiki_prefix


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(
        description="Backlog WikiをMarkdown形式でダウンロード",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 対話モード（推奨）
  backlog-wiki-downloader

  # コマンドライン引数を指定
  backlog-wiki-downloader --url https://xxx.backlog.com --project MYPRJ --api-key YOUR_API_KEY

  # 特定の階層のみダウンロード
  backlog-wiki-downloader --url https://xxx.backlog.com --project MYPRJ --api-key YOUR_API_KEY --prefix "開発/設計書"

  # 出力ディレクトリを指定
  backlog-wiki-downloader --output ./output/Wiki
""",
    )
    parser.add_argument(
        "--url", "-u", help="BacklogスペースURL (例: https://xxx.backlog.com)"
    )
    parser.add_argument("--project", "-p", help="プロジェクトキー (例: MYPRJ)")
    parser.add_argument("--api-key", "-k", help="Backlog APIキー")
    parser.add_argument(
        "--prefix", "-f", default="", help="Wiki階層フィルタ (例: 開発/設計書 または WikiページURL)"
    )
    parser.add_argument(
        "--output", "-o", default="Wiki", help="出力ディレクトリ (デフォルト: Wiki)"
    )

    return parser.parse_args()


def main():
    """メイン関数"""
    try:
        from backlog_wiki_sync import load_config

        args = parse_args()

        # 設定ファイルを読み込み
        config = load_config()

        # 設定ファイル → コマンドライン引数の順で値を決定
        space_url = args.url or config.get("space_url", "")
        project_key = args.project or config.get("project_key", "")
        api_key = args.api_key or config.get("api_key", "")
        wiki_prefix = args.prefix or config.get("wiki_prefix", "")
        output_dir = args.output if args.output != "Wiki" else config.get("output_dir", "Wiki")

        # 必須項目が全て揃っている場合はそのまま使用
        if space_url and project_key and api_key:
            # wiki_prefixがURLの場合は解決
            wiki_prefix = resolve_wiki_prefix(wiki_prefix, space_url, api_key)
        else:
            # 不足している場合は対話モード（既存の値をデフォルトとして使用）
            space_url, project_key, api_key, wiki_prefix = get_user_input(
                default_url=space_url,
                default_project=project_key,
                default_prefix=wiki_prefix,
            )

        # 入力検証
        if not all([space_url, project_key, api_key]):
            print("Error: すべての項目を入力してください")
            sys.exit(1)

        # ダウンローダーを作成して実行
        downloader = BacklogWikiDownloader(
            space_url, api_key, project_key, wiki_prefix, output_dir
        )
        downloader.run()

    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
