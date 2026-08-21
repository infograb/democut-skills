#!/usr/bin/env bash
# 스킬 구조 검증 — 각 스킬 디렉토리에 SKILL.md 가 있고 프론트매터가 온전한지.
set -euo pipefail

fail=0
shopt -s nullglob
for dir in */; do
  case "$dir" in .*/|docs/|scripts/|node_modules/) continue ;; esac
  skill="${dir}SKILL.md"
  if [ ! -f "$skill" ]; then
    echo "✗ $dir : SKILL.md 없음"; fail=1; continue
  fi
  head -1 "$skill" | grep -q '^---$' || { echo "✗ $skill : 프론트매터 시작(---) 없음"; fail=1; }
  for key in name description; do
    grep -q "^${key}:" "$skill" || { echo "✗ $skill : '${key}:' 누락"; fail=1; }
  done
  echo "✓ $skill"
done

if [ "$fail" -ne 0 ]; then
  echo "스킬 검증 실패"; exit 1
fi
echo "모든 스킬 검증 통과"
