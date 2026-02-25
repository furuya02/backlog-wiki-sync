#!/usr/bin/env python3
"""
GitHub Wiki用のファイルを生成するツール

Backlog WikiからダウンロードしたWikiフォルダを、GitHub Wiki形式に変換します。

使い方:
    github-wiki-builder

このツールは以下を実行します:
1. Wikiフォルダから_Sidebar.mdを生成
2. Wikiページと画像をGitHub Wiki形式で出力先にコピー

その後、手動で以下を実行してください:
    cd <output-path>
    git add .
    git commit -m "Update Wiki"
    git push origin master
"""

import argparse
import json
import os
import hashlib
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Any, Set, Optional


# デフォルト設定
DEFAULT_WIKI_PATH = "./Wiki"
DEFAULT_OUTPUT_PATH = "./github-wiki"
DEFAULT_SEPARATOR = " › "
DEFAULT_EXPAND_LEVEL = 2


def load_config() -> Dict[str, Any]:
    """設定ファイルを読み込む"""
    config_path = Path(".github-wiki-builder.json")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """設定ファイルを保存する"""
    config_path = Path(".github-wiki-builder.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def prompt_input(prompt: str, default: Optional[str] = None) -> str:
    """ユーザー入力を取得する"""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    value = input(prompt).strip()
    return value if value else (default or "")


# =============================================================================
# _Sidebar.md 生成
# =============================================================================

def build_tree(wiki_path: str) -> Dict[str, Any]:
    """Wikiフォルダからディレクトリツリーを構築する"""
    tree: Dict[str, Any] = {}

    for root, dirs, files in os.walk(wiki_path):
        if "index.md" not in files:
            continue

        rel_path = os.path.relpath(root, wiki_path)
        if rel_path == ".":
            continue

        parts = rel_path.split(os.sep)
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]

    return tree


def get_link_name(path_parts: List[str], separator: str) -> str:
    """GitHub Wiki用のリンク名を生成する"""
    return separator.join(path_parts)


def get_display_name(folder_name: str) -> str:
    """表示用の名前を取得する"""
    return folder_name.replace("_", " ")


def generate_sidebar_html(
    tree: Dict[str, Any],
    separator: str,
    expand_level: int,
    path_parts: List[str] = None,
    indent: int = 0
) -> str:
    """ディレクトリツリーからサイドバーHTMLを生成する"""
    if path_parts is None:
        path_parts = []

    html_lines: List[str] = []
    indent_str = "  " * indent

    sorted_keys = sorted(tree.keys(), key=lambda x: (
        int(x.split(".")[0].split("_")[0]) if x.split(".")[0].split("_")[0].isdigit() else float('inf'),
        x
    ))

    for key in sorted_keys:
        subtree = tree[key]
        current_path = path_parts + [key]
        display_name = get_display_name(key)
        link_name = get_link_name(current_path, separator)

        if subtree:
            # 指定階層まで展開
            details_tag = '<details open>' if indent < expand_level else '<details>'
            html_lines.append(f'{indent_str}{details_tag}')
            html_lines.append(f'{indent_str}<summary>{display_name}</summary>')
            html_lines.append(f'{indent_str}<ul>')
            sub_html = generate_sidebar_html(subtree, separator, expand_level, current_path, indent + 1)
            html_lines.append(sub_html)
            html_lines.append(f'{indent_str}</ul>')
            html_lines.append(f'{indent_str}</details>')
        else:
            html_lines.append(f'{indent_str}<li><a href="{link_name}">{display_name}</a></li>')

    return "\n".join(html_lines)


def generate_sidebar(wiki_path: str, output_path: str, separator: str, expand_level: int) -> None:
    """_Sidebar.mdを生成する"""
    print("Generating _Sidebar.md...")

    tree = build_tree(wiki_path)
    html = generate_sidebar_html(tree, separator, expand_level)

    sidebar_path = os.path.join(output_path, "_Sidebar.md")
    with open(sidebar_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("  Created: _Sidebar.md")


# =============================================================================
# Wikiページと画像のコピー
# =============================================================================

def get_wiki_page_name(rel_path: str, separator: str) -> str:
    """相対パスからWikiページ名を生成する"""
    return rel_path.replace(os.sep, separator)


def get_safe_image_name(wiki_page_name: str, original_name: str, counter: int) -> str:
    """安全な画像ファイル名を生成する（英数字のみ）"""
    ext = os.path.splitext(original_name)[1].lower()
    hash_input = f"{wiki_page_name}_{original_name}"
    short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"img_{short_hash}_{counter:03d}{ext}"


def clean_old_files(output_path: str) -> None:
    """古いファイルを削除"""
    print("Cleaning old files...")

    # imagesディレクトリを削除
    images_dir = os.path.join(output_path, "images")
    if os.path.exists(images_dir):
        shutil.rmtree(images_dir)
        print("  Removed: images/")

    # 古い画像ファイルとmdファイルを削除
    removed_images = 0
    removed_md = 0
    keep_files = {'_Sidebar.md', 'Home.md', '_Footer.md', '_Header.md'}

    for file in os.listdir(output_path):
        file_path = os.path.join(output_path, file)
        if os.path.isfile(file_path):
            if file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
                os.remove(file_path)
                removed_images += 1
            elif file.endswith('.md') and file not in keep_files:
                os.remove(file_path)
                removed_md += 1

    if removed_images > 0:
        print(f"  Removed: {removed_images} old image files")
    if removed_md > 0:
        print(f"  Removed: {removed_md} old md files")


def copy_wiki_pages(wiki_path: str, output_path: str, separator: str) -> None:
    """Wikiページと画像をコピーする"""
    print("Copying Wiki pages and images...")

    image_extensions: Set[str] = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
    image_counter = 0
    page_counter = 0

    for root, dirs, files in os.walk(wiki_path):
        if "index.md" not in files:
            continue

        rel_path = os.path.relpath(root, wiki_path)
        if rel_path == ".":
            continue

        wiki_page_name = get_wiki_page_name(rel_path, separator)

        index_path = os.path.join(root, "index.md")
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 最初のh1タイトル行を削除（重複回避のため）
        lines = content.split('\n')
        if lines and lines[0].startswith('# '):
            lines = lines[1:]
            # 先頭の空行も削除
            while lines and lines[0].strip() == '':
                lines = lines[1:]
            content = '\n'.join(lines)

        # 画像ファイルをコピーして参照を更新
        for file in files:
            file_lower = file.lower()
            if any(file_lower.endswith(ext) for ext in image_extensions):
                image_counter += 1
                new_image_name = get_safe_image_name(wiki_page_name, file, image_counter)

                src_image = os.path.join(root, file)
                dst_image = os.path.join(output_path, new_image_name)
                shutil.copy2(src_image, dst_image)

                old_ref = f"]({file})"
                new_ref = f"]({new_image_name})"
                content = content.replace(old_ref, new_ref)

        # Markdownを出力
        output_file = os.path.join(output_path, f"{wiki_page_name}.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        page_counter += 1

    print(f"  Copied: {page_counter} pages, {image_counter} images")


# =============================================================================
# メイン処理
# =============================================================================

def main() -> None:
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="Backlog WikiをGitHub Wiki形式に変換するツール"
    )
    parser.add_argument(
        "-i", "--input",
        help="Wikiフォルダのパス（デフォルト: ./Wiki）"
    )
    parser.add_argument(
        "-o", "--output",
        help="出力先のGitHub Wikiリポジトリのパス"
    )
    parser.add_argument(
        "-s", "--separator",
        default=DEFAULT_SEPARATOR,
        help=f"パス区切り文字（デフォルト: '{DEFAULT_SEPARATOR}'）"
    )
    parser.add_argument(
        "-e", "--expand-level",
        type=int,
        default=DEFAULT_EXPAND_LEVEL,
        help=f"サイドバーの展開階層数（デフォルト: {DEFAULT_EXPAND_LEVEL}）"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("GitHub Wiki Builder")
    print("=" * 60)

    # 設定ファイルを読み込み
    config = load_config()

    # 入力パスの決定
    wiki_path = args.input or config.get("wiki_path")
    if not wiki_path:
        wiki_path = prompt_input("Wikiフォルダのパス", DEFAULT_WIKI_PATH)

    # 出力パスの決定
    output_path = args.output or config.get("output_path")
    if not output_path:
        output_path = prompt_input("GitHub Wikiリポジトリのパス", DEFAULT_OUTPUT_PATH)

    # 設定を保存
    config["wiki_path"] = wiki_path
    config["output_path"] = output_path
    save_config(config)

    # パスの検証
    if not os.path.exists(output_path):
        print(f"\nError: {output_path} does not exist.")
        print("Please run 'git clone' first:")
        print(f"  git clone git@github.com:<org>/<repo>.wiki.git {output_path}")
        sys.exit(1)

    if not os.path.exists(wiki_path):
        print(f"\nError: {wiki_path} does not exist.")
        print("Please run 'backlog-wiki-downloader' first.")
        sys.exit(1)

    print()
    print(f"Input:  {wiki_path}")
    print(f"Output: {output_path}")
    print()

    # 古いファイルを削除
    clean_old_files(output_path)

    # _Sidebar.mdを生成
    generate_sidebar(wiki_path, output_path, args.separator, args.expand_level)

    # Wikiページと画像をコピー
    copy_wiki_pages(wiki_path, output_path, args.separator)

    print()
    print("=" * 60)
    print("Done!")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"  cd {output_path}")
    print("  git add .")
    print('  git commit -m "Update Wiki"')
    print("  git push origin master")


if __name__ == "__main__":
    main()
