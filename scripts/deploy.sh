#!/bin/bash
# deploy.sh — QA-gated deploy: fails FAST if the plan data is broken (times/durations/chain)
# repo: aphiwatkr/tokyo-trip-planner (บัญชีส่วนตัว — ย้ายมาจาก aphiwatgo5 เดิม 2026-10-09)
set -e
cd "$(dirname "$0")/.."
gh auth switch -u aphiwatkr >/dev/null 2>&1 || true   # เครื่องนี้มี 2 บัญชี — deploy ตัวนี้ใช้ aphiwatkr
echo "▶ 1/3 QA…"
node scripts/qa.mjs
echo "▶ 2/3 commit…"
git add -A
git -c user.name=aphiwatkr -c user.email=120904377+aphiwatkr@users.noreply.github.com commit -m "deploy: $(date +%F' '%H:%M) — QA-passed" || echo "(nothing to commit)"
echo "▶ 3/3 push…"
git push
echo "✅ pushed — GitHub Pages will deploy in ~1 min: https://aphiwatkr.github.io/tokyo-trip-planner/"
