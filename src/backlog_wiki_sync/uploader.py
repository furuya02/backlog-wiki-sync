#!/usr/bin/env python3
"""
Backlog Wiki Uploader

ローカルのWikiフォルダからBacklogにWikiページをアップロード（上書き）するツール

使用方法:
    backlog-wiki-uploader

機能:
    - memo.mdからBacklog URLとページ名を読み取り
    - 対応するindex.mdの内容をBacklogにアップロード
    - 添付ファイル（画像など）をアップロード
    - Markdown記法をBacklog記法に変換
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Optional
from getpass import getpass
from urllib.parse import urlparse


class BacklogWikiUploader:
    """Backlog Wikiアップローダー"""

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}

    def __init__(
        self,
        space_url: str,
        api_key: str,
        target_wiki_url: str = "",
        wiki_dir: str = "Wiki",
    ):
        """
        初期化

        Args:
            space_url: BacklogスペースURL (例: https://xxx.backlog.com)
            api_key: Backlog APIキー
            target_wiki_url: アップロード対象のWiki URL (空欄で全Wiki)
            wiki_dir: Wikiディレクトリ (デフォルト: "Wiki")
        """
        self.space_url = self._extract_base_url(space_url)
        self.api_key = api_key
        self.target_wiki_id = self.extract_wiki_id_from_url(target_wiki_url) if target_wiki_url else None
        self.wiki_dir = Path(wiki_dir)

    @staticmethod
    def _extract_base_url(url: str) -> str:
        """URLからベースURL（スキーム + ホスト）を抽出"""
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        if not parsed.scheme:
            parsed = urlparse(f"https://{url}")
            return f"{parsed.scheme}://{parsed.netloc}"
        return url.rstrip("/")

    @staticmethod
    def extract_wiki_id_from_url(url: str) -> Optional[int]:
        """URLからWiki IDを抽出"""
        match = re.search(r"/alias/wiki/(\d+)", url)
        if match:
            return int(match.group(1))
        return None

    # ===================
    # API Methods
    # ===================

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

    def _api_patch(self, endpoint: str, data: dict) -> Optional[dict]:
        """API PATCHリクエスト"""
        url = f"{self.space_url}/api/v2/{endpoint}?apiKey={self.api_key}"
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        try:
            request = urllib.request.Request(url, data=encoded_data, method="PATCH")
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            print(f"  API Error: {e.code} - {error_body}")
            return None
        except urllib.error.URLError as e:
            print(f"  Network Error: {e}")
            return None

    def _api_post(self, endpoint: str, data: bytes, content_type: str) -> Optional[dict]:
        """API POSTリクエスト"""
        url = f"{self.space_url}/api/v2/{endpoint}?apiKey={self.api_key}"

        try:
            request = urllib.request.Request(url, data=data, method="POST")
            request.add_header("Content-Type", content_type)
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            print(f"  API Error: {e.code} - {error_body}")
            return None
        except urllib.error.URLError as e:
            print(f"  Network Error: {e}")
            return None

    # ===================
    # Attachment Methods
    # ===================

    def _upload_attachment(self, file_path: Path) -> Optional[int]:
        """添付ファイルをアップロードしてIDを取得"""
        boundary = f"----WebKitFormBoundary{id(self)}"

        with open(file_path, "rb") as f:
            file_content = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + file_content + f"\r\n--{boundary}--\r\n".encode("utf-8")

        result = self._api_post("space/attachment", body, f"multipart/form-data; boundary={boundary}")
        return result.get("id") if result else None

    def _attach_file_to_wiki(self, wiki_id: int, attachment_id: int) -> bool:
        """アップロードした添付ファイルをWikiに関連付け"""
        data = urllib.parse.urlencode({"attachmentId[]": attachment_id}).encode("utf-8")
        result = self._api_post(f"wikis/{wiki_id}/attachments", data, "application/x-www-form-urlencoded")
        return result is not None

    def get_wiki_attachments(self, wiki_id: int) -> list[str]:
        """Wikiページの添付ファイル名一覧を取得"""
        result = self._api_get(f"wikis/{wiki_id}/attachments")
        return [att["name"] for att in result] if result else []

    def upload_attachments(self, folder_path: Path, wiki_id: int, dry_run: bool = False) -> int:
        """フォルダ内の添付ファイルをアップロード"""
        existing = set(self.get_wiki_attachments(wiki_id)) if not dry_run else set()
        uploaded_count = 0

        for file_path in folder_path.iterdir():
            if file_path.suffix.lower() not in self.IMAGE_EXTENSIONS:
                continue
            if file_path.name in existing:
                continue

            if dry_run:
                print(f"    Would upload: {file_path.name}")
                uploaded_count += 1
            else:
                attachment_id = self._upload_attachment(file_path)
                if attachment_id and self._attach_file_to_wiki(wiki_id, attachment_id):
                    print(f"    Uploaded: {file_path.name}")
                    uploaded_count += 1
                else:
                    print(f"    Failed: {file_path.name}")

        return uploaded_count

    # ===================
    # Content Conversion
    # ===================

    @classmethod
    def convert_markdown_to_backlog(cls, content: str) -> str:
        """MarkdownをBacklog記法に変換"""
        # 画像参照を変換: ![image](filename.png) -> ![image][filename.png]
        content = re.sub(
            r"!\[([^\]]*)\]\(([^)]+)\)",
            lambda m: f"![{m.group(1)}][{m.group(2)}]",
            content
        )

        # 箇条書きを変換（インデントされた - を * に）
        lines = []
        for line in content.split("\n"):
            match = re.match(r"^(\s*)- ", line)
            if match:
                indent = match.group(1)
                nest_level = len(indent) // 2 + 1
                line = "*" * nest_level + " " + line[len(indent) + 2:]
            lines.append(line)

        return "\n".join(lines)

    # ===================
    # Wiki Operations
    # ===================

    def find_wiki_pages(self) -> list[tuple[Path, int, str]]:
        """Wikiディレクトリ内のmemo.mdを検索してWikiページ情報を取得"""
        pages = []

        for memo_path in self.wiki_dir.rglob("memo.md"):
            try:
                with open(memo_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                if len(lines) < 2:
                    print(f"  Warning: {memo_path} has insufficient content, skipping")
                    continue

                url = lines[0].strip()
                page_name = lines[1].strip()

                wiki_id = self.extract_wiki_id_from_url(url)
                if wiki_id is None:
                    print(f"  Warning: Could not extract wiki ID from {url}, skipping")
                    continue

                if self.target_wiki_id is not None and wiki_id != self.target_wiki_id:
                    continue

                pages.append((memo_path.parent, wiki_id, page_name))

            except Exception as e:
                print(f"  Error reading {memo_path}: {e}")

        return pages

    def update_wiki_page(self, wiki_id: int, page_name: str, content: str) -> bool:
        """Wikiページを更新"""
        result = self._api_patch(f"wikis/{wiki_id}", {"name": page_name, "content": content})
        return result is not None

    def process_wiki_page(self, folder_path: Path, wiki_id: int, page_name: str, dry_run: bool = False) -> bool:
        """1つのWikiページを処理"""
        index_path = folder_path / "index.md"

        if not index_path.exists():
            print(f"  Warning: {index_path} not found, skipping")
            return False

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                markdown_content = f.read()
        except Exception as e:
            print(f"  Error reading {index_path}: {e}")
            return False

        # 添付ファイルをアップロード
        uploaded = self.upload_attachments(folder_path, wiki_id, dry_run)
        if uploaded > 0:
            print(f"    {uploaded} file(s) uploaded")

        # MarkdownをBacklog記法に変換してWikiを更新
        if dry_run:
            return True

        backlog_content = self.convert_markdown_to_backlog(markdown_content)
        return self.update_wiki_page(wiki_id, page_name, backlog_content)

    def run(self, dry_run: bool = False) -> None:
        """メイン処理を実行"""
        if not self.wiki_dir.exists():
            print(f"Error: Wiki directory '{self.wiki_dir}' not found.")
            return

        print(f"Scanning wiki pages in '{self.wiki_dir}'...")
        pages = self.find_wiki_pages()

        if not pages:
            if self.target_wiki_id is not None:
                print(f"No wiki page found for ID: {self.target_wiki_id}")
            else:
                print("No wiki pages found.")
            return

        pages = sorted(pages, key=lambda x: x[2])

        print("=" * 60)
        print(f"Found {len(pages)} wiki pages to upload")
        if dry_run:
            print("(Dry-run mode: no changes will be made)")
        print("=" * 60)

        success = 0
        failed = 0

        for i, (folder_path, wiki_id, page_name) in enumerate(pages, 1):
            print(f"[{i}/{len(pages)}] {page_name}")

            if self.process_wiki_page(folder_path, wiki_id, page_name, dry_run):
                print(f"  Done")
                success += 1
            else:
                print(f"  Failed")
                failed += 1

        print("=" * 60)
        print(f"Completed: {success} success, {failed} failed")


# ===================
# CLI Functions
# ===================

def prompt_for_missing(
    api_key: str = "",
    target_wiki_url: str | None = None,
    space_url: str = "",
    show_header: bool = True,
) -> tuple[str, str, str]:
    """
    不足している項目のみをユーザーに問い合わせる

    Args:
        api_key: 現在のAPIキー（空なら問い合わせ）
        target_wiki_url: 対象WikiのURL（Noneなら問い合わせ、空文字は全Wiki）
        space_url: 現在のスペースURL
        show_header: ヘッダーを表示するか
    """
    if show_header:
        print("=" * 60)
        print("Backlog Wiki Uploader")
        print("=" * 60)
        print()

    # APIキーを取得（未設定の場合のみ）
    if not api_key:
        print("APIキーを入力してください")
        print("(個人設定 → API → APIキーの発行で取得できます)")
        api_key = getpass("API Key (入力は表示されません): ").strip()
        print()

    # アップロード対象のWiki URLを取得（Noneの場合のみ問い合わせ）
    if target_wiki_url is None:
        print("アップロードするWikiのURLを入力してください（空欄で全Wiki対象）")
        print("例: https://xxx.backlog.com/alias/wiki/12345")
        target_wiki_url = input("URL: ").strip()
        print()

    # スペースURLを決定
    if target_wiki_url:
        space_url = BacklogWikiUploader._extract_base_url(target_wiki_url)
    elif not space_url:
        print("BacklogスペースのURLを入力してください")
        print("例: https://xxx.backlog.com または https://xxx.backlog.jp")
        space_url = input("URL: ").strip()
        if space_url:
            # ベースURLを抽出（Wiki URLなどが入力されても対応）
            space_url = BacklogWikiUploader._extract_base_url(space_url)
        print()

    return api_key, target_wiki_url or "", space_url


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(
        description="ローカルのWikiをBacklogにアップロード（上書き）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 対話モード（推奨）
  backlog-wiki-uploader

  # 特定のWikiページのみアップロード
  backlog-wiki-uploader --api-key YOUR_API_KEY --target-url "https://xxx.backlog.com/alias/wiki/12345"

  # ドライランモード（実際にはアップロードしない）
  backlog-wiki-uploader --api-key YOUR_API_KEY --target-url "https://xxx.backlog.com/alias/wiki/12345" --dry-run
""",
    )
    parser.add_argument("--api-key", "-k", help="Backlog APIキー")
    parser.add_argument(
        "--target-url", "-t", default="", help="対象WikiのURL (例: https://xxx.backlog.com/alias/wiki/12345)"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="ドライランモード（実際にはアップロードしない）"
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
        api_key = args.api_key or config.get("api_key", "")
        space_url = config.get("space_url", "")

        # target_wiki_urlは設定されているかどうかを区別する（Noneなら問い合わせ）
        if args.target_url:
            target_wiki_url = args.target_url
        elif "target_wiki_url" in config:
            target_wiki_url = config["target_wiki_url"]
        else:
            target_wiki_url = None  # 設定がないので問い合わせる

        # 不足している項目を問い合わせ
        api_key, target_wiki_url, space_url = prompt_for_missing(
            api_key=api_key,
            target_wiki_url=target_wiki_url,
            space_url=space_url,
        )

        if not all([api_key, space_url]):
            print("Error: すべての項目を入力してください")
            sys.exit(1)

        uploader = BacklogWikiUploader(space_url, api_key, target_wiki_url)
        uploader.run(dry_run=args.dry_run)

    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
