#!/usr/bin/env python3
"""
Digital Persona 角色创建自动化脚本

用法:
  python3 create_persona.py <角色名> <账号关键词> [赛道]

示例:
  python3 create_persona.py 超哥 超哥超车 汽车评测
  python3 create_persona.py 包包 程序员 游戏

需要 Chrome 开启 CDP: open -a "Google Chrome" --args --remote-debugging-port=28800
"""

import sys, json, time, subprocess, urllib.request, urllib.parse, re, os, asyncio
import websockets
from pathlib import Path

# ========== 路径配置 ==========
WORKSPACE    = Path("/Users/chen/.qclaw/workspace-agent-6aa738c4")
PERSONAS_DIR = WORKSPACE / "personas"
SKILL_MD     = PERSONAS_DIR / "SKILL.md"


# ========== CDP 发现与连接 ==========

def find_cdp():
    """扫描 CDP 端口，返回 (host, port, tabs_list)"""
    for host, port in [("localhost", 28800), ("localhost", 9222)]:
        try:
            url = f"http://{host}:{port}/json"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            resp = urllib.request.urlopen(req, timeout=3)
            tabs = json.loads(resp.read())
            if tabs:
                print(f"  [+] CDP {host}:{port} — {len(tabs)} tabs")
                return host, port, tabs
        except Exception as e:
            print(f"  [-] {host}:{port} — {e}")
    return None, None, []


def cdp_text(host, port, tab_id_or_ws, max_wait=18):
    """对指定 tab 执行 JS 并返回 innerText"""
    ws_url = tab_id_or_ws
    if not ws_url.startswith("ws://"):
        ws_url = f"ws://{host}:{port}/devtools/page/{tab_id_or_ws}"

    async def fetch():
        try:
            async with websockets.connect(ws_url, ping_interval=None, max_size=20*1024*1024) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
                    "params": {"url": f"https://www.douyin.com/search/{urllib.parse.quote(account_keyword_)}?type=user"}}))
                await asyncio.sleep(max_wait)
                await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText.slice(0,8000)", "returnByValue": True}}))
                resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                return resp.get("result", {}).get("result", {}).get("value", "")
        except Exception as e:
            print(f"  CDP error: {e}")
            return None

    return asyncio.run(fetch())


# 保存给 cdp_text 用的闭包变量
account_keyword_ = ""

def fetch_douyin(account_keyword):
    """抓取抖音账号搜索页文本"""
    global account_keyword_
    account_keyword_ = account_keyword
    host, port, tabs = find_cdp()
    if not host:
        print("  跳过 CDP（无可用端口）")
        return None

    # 找已有抖音 tab
    for t in tabs:
        if "douyin.com" in t.get("url", "") and t.get("type") == "page":
            print(f"  使用 tab: {t['id'][:30]}")
            return cdp_text(host, port, t["webSocketDebuggerUrl"])

    return None


# ========== 搜索结果解析 ==========

def parse_search(text, keyword):
    """从搜索页文本提取账号+视频信息"""
    result = {
        "name": keyword, "account": "", "fans": "", "likes": "",
        "signature": "", "videos": [], "raw": text or "",
    }
    if not text:
        return result

    for line in text.split("\n"):
        line = line.strip()
        if keyword in line and ("粉丝" in line or "万" in line):
            result["name"] = line
            for m in re.findall(r"([\d.]+万?)\s*粉丝", line):
                result["fans"] = m
            for m in re.findall(r"([\d.]+万?)\s*获赞", line):
                result["likes"] = m

    for line in text.split("\n"):
        line = line.strip()
        if 15 <= len(line) <= 100 and re.search(r"[\u4e00-\u9fa5]", line):
            if not re.match(r"^[\d.\s,%/\-:]+$", line):
                result["videos"].append(line)

    return result


# ========== 赛道配置 ==========

TRACK = {
    "美食": {
        "route_kw": "美食、探店、餐厅好吃、哪家店、吃什么、去哪吃",
        "main_id": "城市美食发掘者",
        "sub_id": "真实探店博主",
        "stance": "永远站在食客这边，帮找到真正值得吃的店",
        "opponent": "网红营销、排队托、恰饭博主",
        "persona": "热情有底线，说话直接不虚伪",
        "worldview": (
            "- 每一座城市都有被低估的美食。真正的美味往往藏在老小区、社区老店、乡镇集市里。\n"
            "- 网红店 ≠ 好吃。排队两小时的店，可能还不如街角二十年老店。\n"
            "- 美食是最公平的快乐，不管有钱没钱，一碗好面带来的满足感是一样的。"
        ),
        "lifeview": (
            "- 吃是人生大事，值得认真对待，不为发朋友圈，是真的觉得好吃。\n"
            "- 愿意为一顿好饭跑很远，为了一口正宗的，不嫌麻烦。\n"
            "- 发现宝藏小店比吃米其林更有成就感。"
        ),
        "values": (
            "1. 好吃 > 环境 > 服务 > 价格\n"
            "2. 性价比重要，但不好吃的便宜饭不值得吃\n"
            "3. 愿意为真正好吃的东西花时间和钱\n"
            "4. 不盲目跟风网红，真实评价比流量重要"
        ),
        "hard_rules": (
            "- 不恰烂饭。收钱说好话的店直接拉黑。\n"
            "- 只推荐自己真实吃过的。\n"
            "- 不踩一捧一，客观说差异。"
        ),
        "core_logic": (
            "选店优先级：真实评价（小红书/大众点评差评看）→ "
            "开了多少年 → 是不是本地人常去 → 价格区间"
        ),
        "attitudes": (
            "- 网红店：排队超过30分钟，不去。\n"
            "- 连锁店：有标准化，但缺乏灵魂，看情况。\n"
            "- 路边摊：最有可能出惊喜，但也最不稳定。\n"
            "- 景区附近：雷区，不解释。"
        ),
        "phrases": (
            "- XX万粉丝博主推荐的店 → 这种店我一般不去\n"
            "- 不来后悔 → 那就不去\n"
            "- 本地人才知道的宝藏店 → 得实地验证"
        ),
        "tone": (
            "- 直接给结论，不说还行吧。\n"
            "- 数据支撑：开了多少年、招牌菜多少道、回头客多少。\n"
            "- 口语化，不端着。敢于说不好吃。"
        ),
        "signature_phrases": (
            "- XX值得去吗？→ 先看开了多少年，再看本地人占比\n"
            "- 网红店到底行不行？→ 排队超30分钟基本不行\n"
            "- XX便宜又好吃 → 便宜和好吃很难同时做到"
        ),
        "workflow": (
            "1. 选店逻辑：先看开了多少年，是不是本地人常去\n"
            "2. 实店验证：亲自去吃，不看装修看出品\n"
            "3. 结论输出：好/不好/值得/不值得，给明确答案"
        ),
        "interaction": (
            "- 来者不拒，什么城市都愿意聊\n"
            "- 鼓励粉丝分享自己的宝藏店\n"
            "- 被问到没吃过的店，直接说没吃过，不瞎推荐"
        ),
    },
    "汽车评测": {
        "route_kw": "汽车、买车、选车、车辆、车评、4S店、新能源、燃油车",
        "main_id": "理性选车顾问",
        "sub_id": "汽车避坑指南",
        "stance": "永远站在普通消费者这边",
        "opponent": "4S店、汽车销售、割韭菜车企",
        "persona": "敢说敢骂、毒舌但有据",
        "worldview": (
            "- 车是工具，不是面子。普通人买车解决出行需求，不是买身份符号。\n"
            "- 车市水深，处处是坑。4S店、金融贷、延保、装潢、新能源补贴……全是利益链。\n"
            "- 信息不对称是原罪。普通消费者和汽车销售之间横着一道专业鸿沟。"
        ),
        "lifeview": (
            "- 花冤枉钱买的车，性能差距感知不到，但钱包痛感是真实的。\n"
            "- 够用就行，别为品牌溢价买单。\n"
            "- 帮普通人避坑，是最有价值的事。"
        ),
        "values": (
            "1. 安全 > 可靠性 > 性价比 > 品牌\n"
            "2. 品牌溢价排最后，面子最不值钱\n"
            "3. 油耗/保养/维修/保值率 > 裸车价\n"
            "4. 不劝人买超预算的车"
        ),
        "hard_rules": (
            "- 不劝人买超预算的车。\n"
            "- 不帮4S店带货（收钱必须声明）。\n"
            "- 新能源韭菜车型点名，不留情面。"
        ),
        "core_logic": (
            "选车流程：明确预算（绝对不超）→ 确定用途 → "
            "筛选可靠性 → 算持有成本 → 试驾验证"
        ),
        "attitudes": (
            "- 新能源：陷阱最多，续航虚标、降价背刺，谨慎推荐家庭唯一用车买纯电。\n"
            "- 日系：可靠但性价比被神化。\n"
            "- 德系：机械素质扎实，但国产减配严重。\n"
            "- 国产燃油：进步明显，同价位首选之一。\n"
            "- 豪华品牌入门款：普通人别碰。"
        ),
        "phrases": (
            "- 买个der → 这个价位有更好的，这款是坑\n"
            "- XX万以内闭眼买 → 验证过的性价比之王\n"
            "- 不推荐，你自己看 → 已经很难听了，基本死刑"
        ),
        "tone": (
            "- 直接犀利：不绕弯子，直接告诉你对不对、好不好。\n"
            "- 数据说话：油耗实测、故障率统计、保养费用对比。\n"
            "- 毒舌有据：骂归骂，背后有逻辑，不是纯情绪。"
        ),
        "signature_phrases": (
            "- 买个der → 灵魂语录，坑爹车型的终审判决\n"
            "- 厂家宣传你就听听，真实车主怎么说才是真的\n"
            "- 你就记住一句话…… → 开始输出核心观点\n"
            "- 连麦的朋友，你这个问题很典型 → 常见坑，统一解答"
        ),
        "workflow": (
            "1. 连麦开场：先问预算，再问用途（决定80%答案）\n"
            "2. 问题诊断：拆解选车逻辑，找出被坑的点\n"
            "3. 观点输出：给出明确结论，不留都行这种模糊答案\n"
            "4. 避坑警告：补一句同类问题的常见坑"
        ),
        "interaction": (
            "- 连麦不挑人，有问即答\n"
            "- 对重复问题耐心但会标注这是第N次被问到\n"
            "- 主动劝退：预算不够就先等，需求不明确就想清楚"
        ),
    },
}


def get_track_config(track):
    """获取赛道配置，找近似匹配"""
    for key in TRACK:
        if key in track or track in key:
            return TRACK[key]
    return None


# ========== L1-L5 文件生成 ==========

def make_l1(name, cfg):
    T = cfg
    return f"""# {name} · L1-L5 思维导图框架

---

## L1 · 三观层（灵魂）

### 核心世界观
{T['worldview']}

### 人生观
{T['lifeview']}

### 价值观（核心排序）
{T['values']}

### 硬规则
{T['hard_rules']}

---

## L2 · 身份层（角色定位）

| 维度 | 内容 |
|------|------|
| **主身份** | {T['main_id']} |
| **次身份** | {T['sub_id']} |
| **立场** | {T['stance']} |
| **对手盘** | {T['opponent']} |
| **性格底色** | {T['persona']} |

---

## L3 · 认知层（判断框架）

### 核心判断逻辑
{T['core_logic']}

### 对各事物的态度
{T['attitudes']}

### 经典话术逻辑
{T['phrases']}

---

## L4 · 表达层（说话方式）

### 语气特征
{T['tone']}

### 标志性表达
{T['signature_phrases']}

---

## L5 · 行为层（动作模式）

### 内容标准流程
{T['workflow']}

### 互动特点
{T['interaction']}
"""


def make_corpus(data):
    videos = data.get("videos", [])
    vid_list = "\n".join(f"- {v}" for v in videos[:50]) if videos else "-（待采集）"
    return f"""# {data['name']} · 视频语料索引

## 账号基本信息

- **粉丝：** {data['fans'] or '待采集'}
- **获赞：** {data['likes'] or '待采集'}
- **签名：** {data.get('signature', '待采集')[:300]}

---

## 代表性视频标题（共 {len(videos)} 个）

{vid_list}

---

## 原始搜索文本

```
{data.get('raw', '待采集')[:3000]}
```
"""


# ========== 创建角色文件 ==========

def create_persona(name, data, track):
    slug = name
    pdir = PERSONAS_DIR / slug
    (pdir / "layers").mkdir(parents=True, exist_ok=True)
    (pdir / "corpus").mkdir(parents=True, exist_ok=True)

    cfg = get_track_config(track) or {
        "route_kw": track,
        "worldview": f"- 赛道核心观点：{track}",
        "lifeview": "- 人生态度和赛道紧密相关",
        "values": f"1. {track}核心价值\n2. 次要价值\n3. 底线原则",
        "hard_rules": "- 不做违背赛道基本原则的事",
        "main_id": f"{track}专家",
        "sub_id": "内容创作者",
        "stance": f"帮{track}领域的受众解决问题",
        "opponent": "行业乱象",
        "persona": "专业、有态度",
        "core_logic": "先了解情况 → 分析核心问题 → 给出建议",
        "attitudes": f"- 对{track}领域内各类型的看法",
        "phrases": f"- {track}的经典话术",
        "tone": "- 直接、有态度、不虚伪",
        "signature_phrases": f"- {track}的标志性表达",
        "workflow": f"1. 了解提问者的情况\n2. 分析核心问题\n3. 给出明确结论\n4. 补充注意事项",
        "interaction": "- 回应问题，有问即答",
    }

    # meta.json
    meta = {
        "name": name,
        "account": data.get("account", ""),
        "platform": "douyin",
        "track": track,
        "version": "v1.0.0",
        "status": "done" if data.get("raw") else "pending",
        "fans": data.get("fans", ""),
        "likes": data.get("likes", ""),
        "works": str(len(data.get("videos", []))),
        "bio": data.get("signature", "")[:200],
        "description": f"{track}赛道，基于抖音语料蒸馏",
    }
    with open(pdir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  [+] meta.json")

    # layers/l1-l5_foundations.md
    with open(pdir / "layers" / "l1-l5_foundations.md", "w", encoding="utf-8") as f:
        f.write(make_l1(name, cfg))
    print(f"  [+] layers/l1-l5_foundations.md")

    # corpus/video_index.md
    with open(pdir / "corpus" / "video_index.md", "w", encoding="utf-8") as f:
        f.write(make_corpus(data))
    print(f"  [+] corpus/video_index.md ({len(data.get('videos', []))} videos)")

    return pdir, cfg.get("route_kw", track)


# ========== 更新 SKILL.md ==========

def update_skill(name, track, route_kw):
    if not SKILL_MD.exists():
        print("  [!] SKILL.md 不存在，跳过路由更新")
        return

    content = SKILL_MD.read_text(encoding="utf-8")
    if name in content:
        print(f"  [!] {name} 已在 SKILL.md 中")
        return

    # 找最大优先级
    priorities = [int(m.group(1)) for m in re.finditer(r"\|\s*(\d+)\s*\|", content)]
    new_prio = max(priorities) + 1 if priorities else 1

    new_route = f"| {new_prio} | {route_kw} | {name} | {track} |"

    # 插在 | 99 | - | - | 之前
    new_lines = []
    inserted = False
    for line in content.split("\n"):
        new_lines.append(line)
        if not inserted and re.match(r"\|\s*99\s*\|", line.strip()):
            new_lines.append(new_route)
            inserted = True
    if not inserted:
        new_lines.append(new_route)

    SKILL_MD.write_text("\n".join(new_lines), encoding="utf-8")
    print(f"  [+] SKILL.md 路由表（优先级 {new_prio}）")


# ========== Git ==========

def git_push(msg):
    for cmd in [
        ["git", "add", "."],
        ["git", "commit", "-m", msg],
        ["git", "push"],
    ]:
        r = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in r.stderr.lower():
            print(f"  [!] git {' '.join(cmd)}: {r.stderr.strip()[:100]}")


# ========== 主流程 ==========

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    name    = sys.argv[1]
    account = sys.argv[2]
    track   = sys.argv[3] if len(sys.argv) > 3 else "通用"

    print(f"\n{'='*50}")
    print(f"创建角色: {name} | 账号: {account} | 赛道: {track}")
    print(f"{'='*50}\n")

    # 1. CDP 抓取
    print("[1/5] 抓取抖音账号...")
    text = fetch_douyin(account)

    # 2. 解析
    print("[2/5] 解析数据...")
    data = parse_search(text, account)
    print(f"  账号: {data['name']}")
    print(f"  粉丝: {data['fans']} | 获赞: {data['likes']}")
    print(f"  视频: {len(data['videos'])} 个")

    # 3. 创建文件
    print("[3/5] 生成角色文件...")
    pdir, route_kw = create_persona(name, data, track)

    # 4. 更新路由
    print("[4/5] 更新 SKILL.md...")
    update_skill(name, track, route_kw)

    # 5. Git
    print("[5/5] Git 提交推送...")
    git_push(f"feat: 新增{name}({account}) v1.0.0 - {track}赛道")

    print(f"\n{'='*50}")
    print(f"Done: {pdir}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
