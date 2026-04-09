#!/usr/bin/env python3
"""
Digital Persona 标准化角色创建脚本

流程:
  1. 账号发现与验证
  2. 六类内容采集（账号信息/标题/字幕/评论/标签/直播）
  3. 语料分析 + L1-L5 建模
  4. 生成角色文件
  5. 更新 SKILL.md 路由

用法:
  python3 create_persona.py <角色名> <账号关键词> <赛道> <关键词1/关键词2/...>

示例:
  python3 create_persona.py 勇哥 勇哥餐饮创业说 餐饮创业 餐饮/创业/开店/加盟/选址
  python3 create_persona.py 老邪 正经的老谢 鉴渣价值观 女生/恋爱/鉴渣/精致/渣男

前置:
  Chrome 开启 CDP: open -a "Google Chrome" --args --remote-debugging-port=28800
"""

import sys, json, time, re, os, asyncio, urllib.request, urllib.parse
import websockets
from pathlib import Path

# ========== 路径配置 ==========
WORKSPACE    = Path("/Users/chen/.qclaw/workspace-agent-6aa738c4")
PERSONAS_DIR = WORKSPACE / "personas"
SKILL_MD     = PERSONAS_DIR / "SKILL.md"
SCRIPTS_DIR  = WORKSPACE / "scripts"

# ========== 采集配置 ==========
CDP_PORTS = [28800, 9222]
MAX_WAIT   = 18
MAX_TITLES = 300   # 目标视频标题数量
MAX_COMMENTS = 60  # 目标评论数量
MIN_TITLES = 100   # 最低标题数
MIN_COMMENTS = 30  # 最低评论数
MIN_TALKS = 30     # 最低口头禅数

# ========== CDP 工具函数 ==========

def list_tabs(port):
    """返回 [(id, url, type)]"""
    try:
        req = urllib.request.Request(f"http://localhost:{port}/json",
            headers={"User-Agent": "curl/7.68.0"})
        resp = urllib.request.urlopen(req, timeout=3)
        tabs = json.loads(resp.read())
        return [(t["id"], t.get("url",""), t.get("type","")) for t in tabs]
    except Exception:
        return []

def new_tab(port):
    """创建新 tab，返回 tab_id"""
    try:
        req = urllib.request.Request(f"http://localhost:{port}/json/new",
            headers={"User-Agent": "curl/7.68.0"},
            method="PUT")
        resp = urllib.request.urlopen(req, timeout=5)
        tab = json.loads(resp.read())
        return tab.get("id")
    except Exception:
        return None

def ws_eval(ws, rid, expr, timeout=12):
    """通过 WebSocket 执行 JS，返回文本结果"""
    ws.send(json.dumps({"id": rid, "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True}}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv(timeout=deadline - time.time()))
            if msg.get("id") == rid:
                return msg.get("result", {}).get("result", {}).get("value", "")
        except Exception:
            break
    return ""

async def ws_navigate(ws, url, wait=12):
    """导航并等待加载"""
    await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
        "params": {"url": url}}))
    await asyncio.sleep(wait)

async def ws_scroll(ws, times=5, step=800):
    """滚动页面加载更多内容"""
    for _ in range(times):
        await ws.send(json.dumps({"id": 99, "method": "Runtime.evaluate",
            "params": {"expression": f"window.scrollBy(0, {step})"}}))
        await asyncio.sleep(1.5)

# ========== 采集函数 ==========

async def fetch_profile_page(tab_id, port, keyword):
    """抓取抖音账号主页，返回 (账号信息文本, 视频标题列表)"""
    ws_url = f"ws://localhost:{port}/devtools/page/{tab_id}"
    try:
        async with websockets.connect(ws_url, ping_interval=None, max_size=20*1024*1024) as ws:
            # 1. 账号搜索结果页
            await ws_navigate(ws,
                f"https://www.douyin.com/search/{urllib.parse.quote(keyword)}?type=user", wait=12)
            text = await ws_eval(ws, 2, "document.body.innerText.slice(0, 12000)", timeout=15)
            titles = []

            # 2. 尝试进入账号主页抓视频标题
            # 从搜索结果中找到账号主页 URL
            profile_url = await ws_eval(ws, 3, """
(function(){
  var as = document.querySelectorAll('a[href*="/user/"]');
  for(var a of as){
    var t = a.innerText || '';
    if(t.includes('粉丝') && a.href.includes('douyin.com')) return a.href;
  }
  return '';
})()
""")
            
            if profile_url and "douyin.com" in str(profile_url):
                await ws_navigate(ws, profile_url, wait=12)
                await ws_scroll(ws, times=6)
                # 提取视频标题
                titles_raw = await ws_eval(ws, 5, """
(function(){
  var items = document.querySelectorAll('[class*="video"], [class*="Video"], [class*="item"], [class*="Item"], [class*="scroll"], [class*="Scroll"]');
  var lines = [];
  items.forEach(item => {
    var t = item.innerText.trim();
    var parts = t.split(/\\n/).filter(l => l.trim().length > 5 && l.trim().length < 80 && /[\\u4e00-\\u9fa5]/.test(l));
    if(parts.length > 0) lines.push(parts[0]);
  });
  var seen = new Set();
  var unique = [];
  lines.forEach(l => { if(!seen.has(l) && unique.length < 500){ seen.add(l); unique.push(l); }});
  return unique.slice(0,300).join('\\n');
})()
""")
                if titles_raw:
                    titles = [l.strip() for l in str(titles_raw).split('\n') if l.strip()]
            
            return text, titles
    except Exception as e:
        print(f"    [!] CDP error: {e}")
        return "", []

async def fetch_video_comments(tab_id, port, video_count=10):
    """从账号视频列表抓高赞评论"""
    ws_url = f"ws://localhost:{port}/devtools/page/{tab_id}"
    comments = []
    try:
        async with websockets.connect(ws_url, ping_interval=None, max_size=20*1024*1024) as ws:
            # 先到主页
            await ws_navigate(ws, "https://www.douyin.com", wait=8)
            await ws_scroll(ws, times=3)
            text = await ws_eval(ws, 3, "document.body.innerText.slice(0, 5000)")
            return text
    except Exception as e:
        print(f"    [!] Comments fetch error: {e}")
        return ""

def collect_via_http(port, keyword):
    """通过 HTTP + JS 注入采集（备用方案）"""
    tab_id = new_tab(port)
    if not tab_id:
        return {}
    try:
        # 使用 page_snapshot.py
        import subprocess, shutil
        snap = None
        for root in [Path.home() / ".qclaw", Path("/Applications")]:
            for p in root.rglob("page_snapshot.py"):
                snap = str(p)
                break
        if not snap:
            return {}
        # 直接用 curl 调用 CDP
        result = {}
        return result
    except Exception:
        return {}

# ========== 分析函数 ==========

def extract_account_info(text):
    """从搜索页/主页文本中提取账号信息"""
    info = {}
    lines = text.split('\n')
    
    # 提取粉丝/获赞
    粉丝_match = re.search(r'([\\d万]+)万粉丝', text)
    获赞_match = re.search(r'([\\d万\\.]+)亿获赞|([\\d万]+)万获赞', text)
    
    if 粉丝_match:
        info['粉丝'] = 粉丝_match.group(0)
    if 获赞_match:
        info['获赞'] = 获赞_match.group(0)
    
    # 提取签名
    sig_match = re.search(r'((?:关注|抖音号)[^\\n]{5,200})', text)
    if sig_match:
        info['签名'] = sig_match.group(0).strip()
    
    return info

def extract_video_titles(text):
    """从页面文本中提取视频标题"""
    lines = text.split('\n')
    titles = []
    for line in lines:
        line = line.strip()
        # 过滤：太短、太长、无中文、非标题特征
        if (5 < len(line) < 80 and 
            re.search(r'[\u4e00-\u9fa5]', line) and
            not re.match(r'^(精选|推荐|搜索|关注|朋友|我的|直播|放映厅|短剧|综合|视频|用户)', line) and
            not re.match(r'^[\d\s\.,%:/\\-]+$', line) and
            not re.match(r'^(抖音|今日头条|西瓜)', line) and
            'tab' not in line.lower()):
            titles.append(line)
    
    # 去重
    seen = set()
    unique = []
    for t in titles:
        if t not in seen and len(unique) < 500:
            seen.add(t)
            unique.append(t)
    return unique

def extract_catchphrases(titles, profile_text, comments):
    """从标题+主页文本+评论中提取口头禅"""
    all_text = profile_text + '\n'.join(titles[:100]) + (comments or '')
    
    # 模式匹配：短句、感叹、反问、金句
    patterns = [
        r'[^。！？\n]{3,25}[吗呢啊吧呀地得的啦咯诶哦噢嘻嘿哈]',  # 语气结尾
        r'["""]([^"""]+)["""]',  # 引号内容
        r'[^\u4e00-\u9fa5]{0,5}([\u4e00-\u9fa5]{2,8})[^\u4e00-\u9fa5]{0,5}([\u4e00-\u9fa5]{2,8})',  # 短词组合
    ]
    
    # 从 hashtag 中提取
    hashtags = re.findall(r'#([^#\s]{2,20})#?', all_text)
    
    # 从标题中提取短句（5-20字）
    short_phrases = []
    for t in titles:
        if 5 <= len(t) <= 20 and re.search(r'[\u4e00-\u9fa5]{3,}', t):
            short_phrases.append(t)
    
    # 合并去重
    all_phrases = list(set(hashtags + short_phrases))
    # 过滤太长的和太短的
    filtered = [p for p in all_phrases if 2 <= len(p) <= 25 and re.search(r'[\u4e00-\u9fa5]', p)]
    
    return filtered[:80]  # 最多返回80条

def extract_tags(titles, profile_text):
    """从视频标题和主页文本中提取话题标签"""
    # 从 hashtag 提取
    all_text = profile_text + '\n'.join(titles)
    tags = re.findall(r'#([^#\s]{1,20})', all_text)
    
    # 统计频率
    from collections import Counter
    counter = Counter(tags)
    return [(tag, count) for tag, count in counter.most_common(50)]

# ========== L1-L5 生成函数 ==========

def build_l1(text, titles, tags):
    """L1 三观层"""
    tag_str = ' '.join([t[0] for t in tags[:20]])
    return f"""## L1 · 三观层（灵魂）

> 从 {len(titles)} 条视频标题 + 标签分析生成 | 待人工校验

### 核心世界观
- （从语料分析提取，标注「待补充」表示需人工确认）

### 人生观
- （从语料分析提取，标注「待补充」表示需人工确认）

### 价值观
- 核心排序：（从语料分析提取）

### 硬规则
- （从语料中提取行为底线和原则）

### 高频标签：{tag_str[:200]}
"""

def build_l2(titles, tags, talks):
    """L2 身份层"""
    top_talks = talks[:30]
    talks_md = '\n'.join([f'- **{t}** — 口头禅' for t in top_talks[:20]])
    return f"""## L2 · 身份层（角色定位）

| 维度 | 内容 |
|------|------|
| **主身份** | （待填写） |
| **次身份** | （待填写） |
| **立场** | （待填写） |
| **对手盘** | （待填写） |
| **性格底色** | （待填写） |

### 标志性口头禅（{len(top_talks)}条）
{talks_md}

### 常用句式模板
- （从语料中提取3-5个常用句式）
"""

def build_l3(titles, tags):
    """L3 认知层"""
    top_titles = titles[:30]
    titles_md = '\n'.join([f'- {t}' for t in top_titles])
    return f"""## L3 · 认知层（判断框架）

### 核心判断框架
- （从内容主题中提取选品/判断逻辑）

### 主要内容主题（{len(top_titles)}条代表性标题）
{titles_md}

### 话题热度（Top20标签）
{chr(10).join([f'- #{t[0]}（{t[1]}次）' for t in tags[:20]])}

### 常见问题类型
- （从标题和问题类内容中提取）
"""

def build_l4(titles, talks):
    """L4 表达层"""
    talks_str = '、'.join(talks[:15])
    return f"""## L4 · 表达层（说话方式）

### 语气特征
- （从语料中分析语气特点）

### 标志性口头禅
- {talks_str}
- （共{len(talks)}条，超出部分见meta.json signature_phrases）

### 句式结构
```
【诊断式】（描述问题→分析→结论）
【吐槽式】（现象→拆解→态度）
【建议式】（现状→方案→行动）
```
"""

def build_l5(titles, tags):
    """L5 行为层"""
    return f"""## L5 · 行为层（动作模式）

### 内容产出模式
- （从标题中分析视频结构，如：连麦/测评/对比/盘点）

### 互动特点
- （从语料中分析与受众互动方式）

### 高频行为标签
{chr(10).join([f'#{t[0]}' for t in tags[:15]])}
"""

def build_meta(name, account, platform, track, info, talks):
    """生成 meta.json"""
    fans = info.get('粉丝', '')
    likes = info.get('获赞', '')
    bio = info.get('签名', '')
    sigs = talks[:50]
    
    return {
        "name": name,
        "account": account,
        "platform": platform,
        "track": track,
        "version": "v1.0.0",
        "status": "✅ 语料采集中",
        "fans": fans,
        "likes": likes,
        "works": f"{len(talks)}条口头禅",
        "bio": bio,
        "signature_phrases": sigs,
        "corpus_stats": {
            "视频标题": "待采集",
            "字幕文案": "待采集",
            "高赞评论": "待采集",
            "口头禅": len(sigs)
        },
        "description": f"{track}赛道账号"
    }

# ========== 主流程 ==========

async def create_persona(name, account_keyword, track, keywords_str):
    print(f"\n{'='*50}")
    print(f"  Digital Persona 标准化创建流程")
    print(f"  角色: {name} | 账号: {account_keyword} | 赛道: {track}")
    print(f"{'='*50}")
    
    # 0. 创建目录
    persona_dir = PERSONAS_DIR / name
    layers_dir  = persona_dir / "layers"
    corpus_dir  = persona_dir / "corpus"
    
    for d in [layers_dir, corpus_dir]:
        d.mkdir(parents=True, exist_ok=True)
    print(f"\n[1/5] 目录创建: {persona_dir}")
    
    # 1. 账号发现
    print(f"\n[2/5] 账号发现与验证...")
    profile_text = ""
    titles = []
    comments = ""
    
    # 尝试 CDP 采集
    for port in CDP_PORTS:
        tabs = list_tabs(port)
        if not tabs:
            continue
        print(f"    端口 {port}: {len(tabs)} tabs")
        
        tab_id = new_tab(port)
        if tab_id:
            print(f"    新建 tab: {tab_id[:16]}...")
            profile_text, titles = await fetch_profile_page(tab_id, port, account_keyword)
            if profile_text:
                break
    
    # 分析提取
    info = extract_account_info(profile_text)
    if not titles:
        titles = extract_video_titles(profile_text)
    
    print(f"    账号信息: {info}")
    print(f"    视频标题: {len(titles)} 条")
    
    # 2. 语料分析
    print(f"\n[3/5] 语料分析与建模...")
    tags   = extract_tags(titles, profile_text)
    talks  = extract_catchphrases(titles, profile_text, comments)
    
    print(f"    标签: {len(tags)} 个")
    print(f"    口头禅: {len(talks)} 条")
    
    # 3. 生成文件
    print(f"\n[4/5] 生成角色文件...")
    
    # corpus 文件
    (corpus_dir / "00_profile.md").write_text(
        f"# 账号基础信息\n\n账号: {account_keyword}\n赛道: {track}\n\n信息: {json.dumps(info, ensure_ascii=False)}\n\n原文:\n{profile_text[:5000]}", encoding="utf-8")
    
    (corpus_dir / "01_titles.md").write_text(
        f"# 视频标题（共{len(titles)}条）\n\n" +
        '\n'.join([f'- {t}' for t in titles]), encoding="utf-8")
    
    (corpus_dir / "02_captions.md").write_text(
        "# AI字幕/文案\n\n> 待补充：需进入单个视频页面抓取字幕内容", encoding="utf-8")
    
    (corpus_dir / "03_comments.md").write_text(
        f"# 高赞评论\n\n> 待补充：需进入视频详情页抓取评论区\n\n评论数: 0 / 目标30条", encoding="utf-8")
    
    (corpus_dir / "04_tags.md").write_text(
        "# 话题/标签\n\n" +
        '\n'.join([f'- #{t[0]}（{t[1]}次）' for t in tags[:50]]), encoding="utf-8")
    
    (corpus_dir / "05_live.md").write_text(
        "# 直播连麦语料\n\n> 待补充：需访问直播回放", encoding="utf-8")
    
    # L1-L5 文件
    (layers_dir / "l1_foundations.md").write_text(
        "# L1 · 三观层\n\n" + build_l1(profile_text, titles, tags), encoding="utf-8")
    (layers_dir / "l2_foundations.md").write_text(
        "# L2 · 身份层\n\n" + build_l2(titles, tags, talks), encoding="utf-8")
    (layers_dir / "l3_foundations.md").write_text(
        "# L3 · 认知层\n\n" + build_l3(titles, tags), encoding="utf-8")
    (layers_dir / "l4_foundations.md").write_text(
        "# L4 · 表达层\n\n" + build_l4(titles, talks), encoding="utf-8")
    (layers_dir / "l5_foundations.md").write_text(
        "# L5 · 行为层\n\n" + build_l5(titles, tags), encoding="utf-8")
    
    # meta.json
    meta = build_meta(name, account_keyword, "douyin", track, info, talks)
    (persona_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # 4. 更新 SKILL.md
    print(f"\n[5/5] 更新 SKILL.md 路由...")
    keywords = [k.strip() for k in keywords_str.split('/') if k.strip()]
    
    # 读取现有 SKILL.md
    if SKILL_MD.exists():
        content = SKILL_MD.read_text(encoding="utf-8")
    else:
        content = "# SKILL.md\n"
    
    # 找路由表最后一行，追加新角色
    new_line = f"| N | {'/'.join(keywords[:5])} | {name} | {track} |"
    
    # 简单追加（后续需人工补充优先级数字）
    if "| N |" not in content or name not in content:
        # 在第一个空行或文件末尾追加
        content += f"\n{new_line}\n"
        SKILL_MD.write_text(content, encoding="utf-8")
    
    # 5. 达标检查
    print(f"\n{'='*50}")
    print(f"  采集结果检查")
    print(f"{'='*50}")
    checks = [
        ("视频标题", len(titles), MIN_TITLES, "✅" if len(titles) >= MIN_TITLES else "⚠️"),
        ("口头禅", len(talks), MIN_TALKS, "✅" if len(talks) >= MIN_TALKS else "⚠️"),
        ("字幕文案", 0, 50, "🔴"),
        ("高赞评论", 0, MIN_COMMENTS, "🔴"),
    ]
    for label, got, need, icon in checks:
        status = icon
        if got >= need: status = f"✅ 达标({got}条)"
        elif got > 0:   status = f"⚠️ 不足({got}/{need})"
        else:           status = f"🔴 待采集"
        print(f"  {status} | {label}")
    
    print(f"\n  角色目录: {persona_dir}")
    print(f"  后续请进入 corpus/ 补充字幕和评论")
    
    return {
        "titles": len(titles),
        "talks": len(talks),
        "tags": len(tags),
        "info": info
    }

def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    
    name          = sys.argv[1]
    account_kw    = sys.argv[2]
    track         = sys.argv[3]
    keywords_str  = sys.argv[4] if len(sys.argv) > 4 else track
    
    asyncio.run(create_persona(name, account_kw, track, keywords_str))

if __name__ == "__main__":
    main()
