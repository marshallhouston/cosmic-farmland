#!/usr/bin/env bash
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
total_in=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_out=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
worktree=$(echo "$input" | jq -r '.worktree.name // empty')
rate_5h=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
rate_7d=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

# Claude API status (adaptive cache: 1h when green, 5m when degraded/outage)
cache_file="/tmp/claude_api_status_cache"
api_status=""
if [ -f "$cache_file" ]; then
  now=$(date +%s)
  mtime=$(stat -f %m "$cache_file" 2>/dev/null || echo 0)
  cached_status=$(cat "$cache_file")
  [ "$cached_status" = "operational" ] && ttl=3600 || ttl=300
  if [ $((now - mtime)) -lt $ttl ]; then
    api_status="$cached_status"
  fi
fi
if [ -z "$api_status" ]; then
  api_status=$(curl -sf --max-time 3 "https://status.claude.com/api/v2/components.json" \
    | jq -r '.components[] | select(.id == "k8w3r06qmzrp") | .status' 2>/dev/null)
  [ -n "$api_status" ] && echo "$api_status" > "$cache_file" || api_status="unknown"
fi
case "$api_status" in
  "operational")           api_dot="\033[0;32m●\033[0m" ;;
  "degraded_performance")  api_dot="\033[0;33m●\033[0m" ;;
  "partial_outage")        api_dot="\033[0;33m●\033[0m" ;;
  "major_outage")          api_dot="\033[0;31m●\033[0m" ;;
  *)                       api_dot="\033[0;37m●\033[0m" ;;
esac

# Auto-switch model + effort based on API health (takes effect next session)
settings_file="$HOME/.claude/settings.json"
if [ "$api_status" = "operational" ]; then
  desired_model="opus"; desired_effort="max"
else
  desired_model="sonnet"; desired_effort="high"
fi
current_model=$(jq -r '.model // empty' "$settings_file" 2>/dev/null)
current_effort=$(jq -r '.effortLevel // empty' "$settings_file" 2>/dev/null)
if [ "$current_model" != "$desired_model" ] || [ "$current_effort" != "$desired_effort" ]; then
  tmp=$(mktemp)
  jq --arg m "$desired_model" --arg e "$desired_effort" \
    '.model = $m | .effortLevel = $e' "$settings_file" > "$tmp" \
    && mv "$tmp" "$settings_file"
fi

# Directory basename (cyan, like robbyrussell)
dir=$(basename "$cwd")

# Git branch (blue/red, like robbyrussell)
git_branch=""
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
  branch=$(git -C "$cwd" -c gc.auto=0 symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" -c gc.auto=0 rev-parse --short HEAD 2>/dev/null)
  if [ -n "$branch" ]; then
    git_dirty=""
    if ! git -C "$cwd" -c gc.auto=0 diff --quiet 2>/dev/null || ! git -C "$cwd" -c gc.auto=0 diff --cached --quiet 2>/dev/null; then
      git_dirty="\033[0;33m ✗"
    fi
    git_branch=" \033[1;34mgit:(\033[0;31m${branch}\033[1;34m)${git_dirty}\033[0m"
  fi
fi

# Worktree indicator
worktree_part=""
if [ -n "$worktree" ]; then
  worktree_part=" \033[0;35m[wt: ${worktree}]\033[0m"
fi

# Line 1: dir, git, worktree
printf "\033[0;36m%s\033[0m%b%b\n" "$dir" "$git_branch" "$worktree_part"

# Context progress bar with color thresholds
pct=0
if [ -n "$used" ]; then
  pct=$(printf '%.0f' "$used")
fi
bar_width=10
filled=$((pct * bar_width / 100))
empty=$((bar_width - filled))
bar=""
[ "$filled" -gt 0 ] && printf -v fill "%${filled}s" && bar="${fill// /█}"
[ "$empty" -gt 0 ] && printf -v pad "%${empty}s" && bar="${bar}${pad// /░}"

if [ "$pct" -ge 90 ]; then bar_color="\033[0;31m"
elif [ "$pct" -ge 70 ]; then bar_color="\033[0;33m"
else bar_color="\033[0;32m"; fi

# Format cost
cost_fmt=$(printf '$%.2f' "$cost")

# Format tokens (compact: k for thousands)
fmt_tokens() {
  local n=$1
  if [ "$n" -ge 1000 ]; then
    printf '%s' "$((n / 1000)).$((n % 1000 / 100))k"
  else
    printf '%s' "$n"
  fi
}
in_fmt=$(fmt_tokens "$total_in")
out_fmt=$(fmt_tokens "$total_out")

# Rate limits (color-coded: green < 50%, yellow 50-79%, red 80%+)
rate_part=""
if [ -n "$rate_5h" ]; then
  r5=$(printf '%.0f' "$rate_5h")
  if [ "$r5" -ge 80 ]; then rc="\033[0;31m"
  elif [ "$r5" -ge 50 ]; then rc="\033[0;33m"
  else rc="\033[0;32m"; fi
  rate_part="${rc}5h:${r5}%\033[0m"
fi
if [ -n "$rate_7d" ]; then
  r7=$(printf '%.0f' "$rate_7d")
  if [ "$r7" -ge 80 ]; then rc="\033[0;31m"
  elif [ "$r7" -ge 50 ]; then rc="\033[0;33m"
  else rc="\033[0;32m"; fi
  rate_part="${rate_part:+${rate_part} }${rc}7d:${r7}%\033[0m"
fi

# Line 2: progress bar, cost, tokens, rate limits, model
printf "%b%s\033[0m %s%% \033[0;37m| %s | %s in / %s out\033[0m" \
  "$bar_color" "$bar" "$pct" "$cost_fmt" "$in_fmt" "$out_fmt"
[ -n "$rate_part" ] && printf " \033[0;37m|\033[0m %b" "$rate_part"
printf " \033[0;37m| %s\033[0m %b" "$model" "$api_dot"
