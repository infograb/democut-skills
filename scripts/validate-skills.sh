#!/usr/bin/env bash
# 스킬 구조 검증 — 각 스킬 디렉토리에 SKILL.md 가 있고 프론트매터가 온전한지,
# 프론트매터 name 이 디렉토리명과 같은지, 스킬 스크립트(Python)가 문법상 온전한지.
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
  name="$(sed -n 's/^name:[[:space:]]*//p' "$skill" | head -1)"
  if [ "$name" != "${dir%/}" ]; then
    echo "✗ $skill : name '$name' 이 디렉토리명 '${dir%/}' 과 다름"; fail=1
  fi
  for py in "${dir}"scripts/*.py; do
    if ! python3 -c 'import ast, sys; ast.parse(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1])' "$py"; then
      echo "✗ $py : Python 문법 오류"; fail=1
    fi
  done
  echo "✓ $skill"
done

if [ "$fail" -ne 0 ]; then
  echo "스킬 검증 실패"; exit 1
fi
echo "모든 스킬 검증 통과"
