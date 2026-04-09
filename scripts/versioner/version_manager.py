#!/usr/bin/env python3
"""
version_manager.py — 角色版本管理与回滚工具

用法:
  python3 version_manager.py --action backup --slug yongge --base-dir ./personas
  python3 version_manager.py --action rollback --slug yongge --version v1.0.0 --base-dir ./personas
  python3 version_manager.py --action list --slug yongge --base-dir ./personas
  python3 version_manager.py --action restore-latest --slug yongge --base-dir ./personas
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PERSONA_DIRS = ["personality.md", "capability.md"]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def get_slug_dir(base_dir, slug):
    slug_dir = os.path.join(base_dir, slug)
    if not os.path.isdir(slug_dir):
        print(f"错误：未找到角色目录 {slug_dir}")
        sys.exit(1)
    return slug_dir


def get_meta(slug_dir):
    meta_path = os.path.join(slug_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(slug_dir, meta):
    meta_path = os.path.join(slug_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def increment_version(current_version):
    """v1.0.0 -> v1.0.1"""
    parts = current_version.lstrip("v").split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return "v" + ".".join(parts)


def action_backup(slug, base_dir):
    slug_dir = get_slug_dir(base_dir, slug)
    meta = get_meta(slug_dir)
    current_version = meta.get("version", "v1.0.0")
    new_version = increment_version(current_version)

    versions_dir = os.path.join(slug_dir, "versions")
    os.makedirs(versions_dir, exist_ok=True)

    # 备份版本目录
    version_snapshot_dir = os.path.join(versions_dir, current_version)
    if os.path.exists(version_snapshot_dir):
        shutil.rmtree(version_snapshot_dir)

    os.makedirs(version_snapshot_dir)

    for fname in PERSONA_DIRS:
        src = os.path.join(slug_dir, fname)
        if os.path.exists(src):
            dst = os.path.join(version_snapshot_dir, fname)
            shutil.copy2(src, dst)

    # 复制 meta.json
    meta_src = os.path.join(slug_dir, "meta.json")
    if os.path.exists(meta_src):
        shutil.copy2(meta_src, os.path.join(version_snapshot_dir, "meta.json"))

    # 更新 meta.json 版本号
    meta["version"] = new_version
    meta["updated_at"] = now_iso()
    save_meta(slug_dir, meta)

    print(f"✓ 已备份 {current_version} → 新版本 {new_version}")
    print(f"  快照目录: {version_snapshot_dir}")


def action_rollback(slug, version, base_dir):
    slug_dir = get_slug_dir(base_dir, slug)
    versions_dir = os.path.join(slug_dir, "versions", version.lstrip("v"))

    if not os.path.isdir(versions_dir):
        print(f"错误：未找到版本快照 {version}，目录 {versions_dir}")
        available = [d for d in os.listdir(os.path.join(slug_dir, "versions"))
                     if os.path.isdir(os.path.join(slug_dir, "versions", d))]
        print(f"可用版本：{available}")
        sys.exit(1)

    # 备份当前版本（回滚前）
    meta = get_meta(slug_dir)
    current_version = meta.get("version", "v1.0.0")
    backup_version = increment_version(current_version)
    backup_dir = os.path.join(slug_dir, "versions", "rollback_backup_" + current_version)
    os.makedirs(backup_dir, exist_ok=True)
    for fname in PERSONA_DIRS:
        src = os.path.join(slug_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup_dir, fname))

    # 恢复目标版本
    for fname in PERSONA_DIRS:
        src = os.path.join(versions_dir, fname)
        dst = os.path.join(slug_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    meta["version"] = version
    meta["updated_at"] = now_iso()
    save_meta(slug_dir, meta)

    print(f"✓ 已回滚到 {version}（当前版本已备份为 rollback_backup_{current_version}）")


def action_list(slug, base_dir):
    slug_dir = get_slug_dir(base_dir, slug)
    versions_dir = os.path.join(slug_dir, "versions")
    meta = get_meta(slug_dir)

    print(f"角色：{meta.get('name', slug)}")
    print(f"当前版本：{meta.get('version', 'unknown')}")
    print(f"更新时间：{meta.get('updated_at', 'unknown')}")
    print(f"纠正次数：{meta.get('corrections_count', 0)}")
    print()

    if os.path.isdir(versions_dir):
        versions = sorted([d for d in os.listdir(versions_dir) if not d.startswith("rollback_backup")])
        if versions:
            print("历史版本：")
            for v in versions:
                mtime = os.path.getmtime(os.path.join(versions_dir, v))
                date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                print(f"  {v} ({date})")
        else:
            print("暂无历史版本快照")
    else:
        print("暂无版本管理目录")


def main():
    parser = argparse.ArgumentParser(description="角色版本管理器")
    parser.add_argument("--action", choices=["backup", "rollback", "list", "restore-latest"], required=True)
    parser.add_argument("--slug", required=True, help="角色 slug，如 yongge")
    parser.add_argument("--base-dir", default="./personas", help="personas 目录路径")
    parser.add_argument("--version", help="回滚目标版本，如 v1.0.0")

    args = parser.parse_args()

    if args.action == "rollback" and not args.version:
        print("错误：回滚需要指定 --version")
        sys.exit(1)

    if args.action == "backup":
        action_backup(args.slug, args.base_dir)
    elif args.action == "rollback":
        action_rollback(args.slug, args.version, args.base_dir)
    elif args.action == "list":
        action_list(args.slug, args.base_dir)
    elif args.action == "restore-latest":
        slug_dir = get_slug_dir(args.base_dir, args.slug)
        versions_dir = os.path.join(slug_dir, "versions")
        if os.path.isdir(versions_dir):
            versions = sorted([d for d in os.listdir(versions_dir)
                              if not d.startswith("rollback_backup") and os.path.isdir(os.path.join(versions_dir, d))])
            if versions:
                action_rollback(args.slug, versions[-1], args.base_dir)
            else:
                print("没有可恢复的版本")
        else:
            print("没有版本管理目录")


if __name__ == "__main__":
    main()
