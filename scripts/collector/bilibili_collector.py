#!/usr/bin/env python3
"""
bilibili_collector.py — B站视频/UP主信息采集器

用法:
  python3 bilibili_collector.py --name "勇哥说餐饮" --output ./corpus
  python3 bilibili_collector.py --uid 12345678 --output ./corpus
  python3 bilibili_collector.py --keyword "餐饮创业" --output ./corpus

说明:
  使用 B站官方 API，无需登录即可获取公开信息。
  视频字幕/完整内容需要登录或 B站大会员。
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

API_BASE = "https://api.bilibili.com"


def http_get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Referer": "https://www.bilibili.com",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"code": -1, "message": str(e)}


def search_user(keyword):
    """搜索用户"""
    url = f"{API_BASE}/x/web-interface/search/type"
    data = http_get(url, {
        "search_type": "bili_user",
        "keyword": keyword,
        "page": 1,
    })
    return data.get("data", {}).get("result", []) if data.get("code") == 0 else []


def get_user_info(uid):
    """获取用户基本信息"""
    url = f"{API_BASE}/x/space/acc/info"
    return http_get(url, {"mid": uid})


def get_user_videos(uid, page=1, pagesize=30):
    """获取用户视频列表"""
    url = f"{API_BASE}/x/space/wbi/arc/search"
    data = http_get(url, {
        "mid": uid,
        "pn": page,
        "ps": pagesize,
        "order": "pubdate",
    })
    return data


def get_video_info(bvid):
    """获取视频详情"""
    url = f"{API_BASE}/x/web-interface/view"
    return http_get(url, {"bvid": bvid})


def get_video_tags(bvid):
    """获取视频标签"""
    url = f"{API_BASE}/x/tag/archive/tags"
    return http_get(url, {"aid": bvid})


def get_popular_videos(keyword, page=1):
    """按关键词搜索视频"""
    url = f"{API_BASE}/x/web-interface/search/type"
    data = http_get(url, {
        "search_type": "video",
        "keyword": keyword,
        "page": page,
        "order": "totalrank",
    })
    return data.get("data", {}).get("result", []) if data.get("code") == 0 else []


def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 已保存: {path}")


def save_text(text, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  ✓ 已保存: {path}")


def main():
    parser = argparse.ArgumentParser(description="B站内容采集器")
    parser.add_argument("--name", help="UP主名称关键词")
    parser.add_argument("--uid", type=int, help="UP主 UID")
    parser.add_argument("--keyword", help="视频搜索关键词（与 --name 二选一）")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--max-videos", type=int, default=20, help="最多采集视频数")
    args = parser.parse_args()

    if not args.name and not args.uid and not args.keyword:
        print("错误：需要提供 --name 或 --uid 或 --keyword")
        sys.exit(1)

    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    videos_dir = os.makedirs(os.path.join(output_dir, "videos"), exist_ok=True)
    lives_dir = os.makedirs(os.path.join(output_dir, "lives"), exist_ok=True)

    results = {"collected_at": timestamp, "videos": [], "user_info": None}

    # 方式1：按关键词搜索视频
    if args.keyword:
        print(f"搜索关键词: {args.keyword}")
        for page in range(1, 3):
            videos = get_popular_videos(args.keyword, page)
            if not videos:
                break
            for v in videos[:args.max_videos]:
                bvid = v.get("bvid")
                title = v.get("title", "无标题")
                desc = v.get("description", "")
                author = v.get("author", "")
                play = v.get("play", 0)
                pubdate = v.get("pubdate", 0)

                vid_info = {
                    "bvid": bvid,
                    "title": title,
                    "author": author,
                    "description": desc,
                    "play_count": play,
                    "pubdate": pubdate,
                    "url": f"https://www.bilibili.com/video/{bvid}",
                }
                results["videos"].append(vid_info)

                # 保存单个视频信息
                video_dir = os.path.join(output_dir, "videos", bvid)
                save_json(vid_info, f"{video_dir}/info.json")
                save_text(f"# {title}\n\n作者: {author}\n\n简介: {desc}\n\n链接: https://www.bilibili.com/video/{bvid}",
                         f"{video_dir}/description.md")

            if len(results["videos"]) >= args.max_videos:
                break

    # 方式2：采集指定UP主
    if args.name or args.uid:
        uid = args.uid
        if not uid:
            print(f"搜索UP主: {args.name}")
            users = search_user(args.name)
            if not users:
                print("未找到该UP主，请尝试其他关键词")
                sys.exit(1)
            uid = users[0].get("mid")
            uname = users[0].get("uname", args.name)
            print(f"找到UP主: {uname} (UID: {uid})")

        # 获取用户信息
        user_data = get_user_info(uid)
        if user_data.get("code") == 0:
            uinfo = user_data["data"]
            results["user_info"] = {
                "name": uinfo.get("name"),
                "sex": uinfo.get("sex"),
                "sign": uinfo.get("sign"),
                "fans": uinfo.get("fans", 0),
                "friend": uinfo.get("friend", 0),
                "attention": uinfo.get("attention", 0),
                "level": uinfo.get("level"),
                "official_verify": uinfo.get("official_verify"),
            }
            save_json(results["user_info"], os.path.join(output_dir, "user_info.json"))
            save_text(f"# {results['user_info']['name']}\n\n{results['user_info']['sign']}\n\n粉丝: {results['user_info']['fans']}",
                     os.path.join(output_dir, "user_profile.md"))

        # 获取视频列表
        print(f"采集视频列表 (最多 {args.max_videos} 个)...")
        page = 1
        collected = 0
        while collected < args.max_videos:
            data = get_user_videos(uid, page)
            if data.get("code") != 0:
                print(f"获取视频列表失败: {data.get('message')}")
                break
            vlist = data.get("data", {}).get("list", {}).get("vlist", [])
            if not vlist:
                break
            for v in vlist:
                if collected >= args.max_videos:
                    break
                bvid = v.get("bvid")
                vid_data = {
                    "bvid": bvid,
                    "title": v.get("title"),
                    "description": v.get("description"),
                    "author": v.get("author"),
                    "play": v.get("play"),
                    "comment": v.get("comment"),
                    "pubdate": v.get("pubdate"),
                    "length": v.get("length"),
                    "url": f"https://www.bilibili.com/video/{bvid}",
                }
                results["videos"].append(vid_data)
                video_dir = os.path.join(output_dir, "videos", bvid)
                save_json(vid_data, f"{video_dir}/info.json")
                save_text(f"# {v.get('title')}\n\n作者: {v.get('author')}\n\n时长: {v.get('length')}\n\n播放: {v.get('play')}\n\n简介: {v.get('description')}\n\n链接: https://www.bilibili.com/video/{bvid}",
                         f"{video_dir}/description.md")
                collected += 1
            page += 1

    # 保存采集摘要
    save_json(results, os.path.join(output_dir, "collection_summary.json"))

    print(f"\n✓ 采集完成！")
    print(f"  UP主信息: 1 个")
    print(f"  视频数量: {len(results['videos'])} 个")
    print(f"  输出目录: {output_dir}")


if __name__ == "__main__":
    main()
