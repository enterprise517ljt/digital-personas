# AI字幕/文案

> 🔴 待补充：需要进入单个视频页面抓取字幕内容
> 采集方法：CDP 进入视频页，执行 document.querySelector('video') 所在字幕区的文字

## 采集目标
- [ ] 单条字幕样本 ≥ 50条
- [ ] 每条字幕字数 ≥ 50字
- [ ] 来源：各内容类型的代表性视频

## 采集方法
```bash
# CDP 导航到视频页后执行：
python3 scripts/fetch_caption.py <角色名> <TAB_ID>
```
