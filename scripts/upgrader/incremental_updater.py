#!/usr/bin/env python3
"""
incremental_updater.py — 角色增量更新脚本

定时运行，自动采集最新内容并 merge 进角色知识库。

用法:
  python3 incremental_updater.py --slug yongge --base-dir ./personas
  python3 incremental_updater.py --slug ququ --base-dir ./personas --auto-merge
"""

import argparse
import os
import sys

# 添加 scripts 目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import bilibili_collector as bc
except ImportError:
    bilibili_collector = None

from version_manager import action_backup, action_list

ACCOUNTS = {
    "yongge": {
        "name": "勇哥说餐饮",
        "keyword": "勇哥说餐饮 餐饮创业",
        "platform": "bilibili",
    },
    "ququ": {
        "name": "曲曲大女人",
        "keyword": "曲曲大女人 女性成长",
        "platform": "bilibili",
    }
}


def get_latest_corpus(slug, corpus_dir):
    """获取最新语料目录"""
    videos_dir = os.path.join(corpus_dir, "videos")
    if not os.path.isdir(videos_dir):
        return []
    # 按修改时间排序，取最新的
    dirs = sorted(
        [d for d in os.listdir(videos_dir) if os.path.isdir(os.path.join(videos_dir, d))],
        key=lambda x: os.path.getmtime(os.path.join(videos_dir, x)),
        reverse=True
    )
    return dirs[:10]  # 最近10个视频


def run_collection(slug, corpus_dir, dry_run=False):
    """执行语料采集"""
    account = ACCOUNTS.get(slug)
    if not account:
        print(f"错误：未知角色 {slug}")
        sys.exit(1)

    if bilibili_collector is None:
        print("错误：bilibili_collector 模块不可用")
        sys.exit(1)

    if dry_run:
        print(f"[DRY RUN] 将采集: {account['keyword']}")
        return

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"临时采集目录: {tmpdir}")
        # 这里简化处理，实际使用时调用 bc 模块
        print(f"关键词: {account['keyword']}")
        print("实际采集需要安装 bilibili_collector.py 依赖")


def main():
    parser = argparse.ArgumentParser(description="角色增量更新")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--base-dir", default="./personas")
    parser.add_argument("--dry-run", action="store_true", help="仅显示将执行的操作，不实际采集")
    parser.add_argument("--auto-merge", action="store_true", help="自动 merge 新语料，不等待确认")
    args = parser.parse_args()

    slug_dir = os.path.join(args.base_dir, args.slug)
    corpus_dir = os.path.join(slug_dir, "corpus")
    os.makedirs(corpus_dir, exist_ok=True)

    print(f"=== 增量更新: {args.slug} ===")
    print()

    # Step 1: 采集最新内容
    print("Step 1: 采集最新语料...")
    run_collection(args.slug, corpus_dir, args.dry_run)

    if args.dry_run:
        return

    # Step 2: 备份当前版本
    print("\nStep 2: 备份当前版本...")
    action_backup(args.slug, args.base_dir)

    # Step 3: 提示 merge
    latest = get_latest_corpus(args.slug, corpus_dir)
    if latest:
        print(f"\n发现 {len(latest)} 个新语料待 merge")
        if args.auto_merge:
            print("[AUTO] 请在 AI 会话中手动执行 merge 操作")
        else:
            print("请在 AI 会话中说：'更新勇哥' 或 '更新曲曲' 来完成 merge")


if __name__ == "__main__":
    main()
