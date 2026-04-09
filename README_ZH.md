# 数字生命 Skill 工厂

> 将互联网网红蒸馏成 AI Skill，用他们的声音回答人生问题

---

## 是什么

把真实的互联网内容创作者（网红）蒸馏成 AI Skill。

每个 Skill 由双层结构驱动：

| 层 | 内容 |
|---|---|
| **Persona（性格层）** | L1-L5 五层性格结构：硬规则 → 身份 → 表达风格 → 决策模式 → 人际行为 |
| **Capability（能力层）** | 核心工作能力——望闻问切四步法，帮人解决人生困境 |

**运行逻辑**：`接收问题 → L1-L5 性格判断态度 → Capability 执行 → 用角色声音输出`

---

## 已收录角色

| 角色 | 领域 | 简介 |
|---|---|---|
| [勇哥](./personas/yongge/) | 餐饮 | 抖音@勇哥说餐饮，餐饮从业者的实战导师 |
| [曲曲](./personas/ququ/) | 女性 | 抖音@曲曲大女人，女性成长与情感导师 |

---

## 安装

```bash
git clone https://github.com/<your-username>/digital-personas.git ~/.openclaw/workspace/skills/digital-personas
```

---

## 使用

```
/勇哥   → 调用勇哥角色
/曲曲   → 调用曲曲角色
/更新勇哥 → 增量更新勇哥的语料库
/回滚勇哥 v1.2 → 回滚到 v1.2
```

---

*MIT License*
