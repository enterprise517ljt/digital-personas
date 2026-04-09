#!/bin/bash
# new-persona.sh — 一句话创建角色
# 用法: bash scripts/new-persona.sh <角色名> <抖音账号关键词> [赛道]
#
# 示例:
#   bash scripts/new-persona.sh 超哥 超哥超车 汽车评测
#   bash scripts/new-persona.sh 包包 程序员 游戏
#
# 注意: 需要 Chrome 在 CDP 模式下运行 (--remote-debugging-port=28800)
# 如需自动后台运行 Chrome: open -a "Google Chrome" --args --remote-debugging-port=28800

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

python3 "$SCRIPT_DIR/create_persona.py" "$@"
