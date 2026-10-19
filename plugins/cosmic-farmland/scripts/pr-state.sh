#!/usr/bin/env bash
# pr-state.sh -- one-line PR state for /ship and /ship-all.
#
# Usage: pr-state.sh <pr-number>   -> key=value line, title last
#        pr-state.sh --mine        -> "<number>\t<branch>\t<title>" per open PR you authored, oldest first
#
# Exists so the commands never paste jq with "\(...)" interpolation: Claude
# Code's worktree sandbox refuses those as too complex to verify. (why: 240
# refusals across preach-hub sessions, most of them /ship's state reads.)
#
# fresh= compares the head SHA to scored_sha= in the newest
# "<!-- risk-score: ... -->" comment: yes | no | unscored.
set -euo pipefail

if [ "${1:-}" = "--mine" ]; then
  gh pr list --author "@me" --state open --json number,title,headRefName \
    --jq 'sort_by(.number) | .[] | [.number, .headRefName, .title] | @tsv'
  exit 0
fi

PR="${1:?usage: pr-state.sh <pr-number> | --mine}"
gh pr view "$PR" --json number,state,mergeable,mergeStateStatus,headRefOid,headRefName,title,labels,comments --jq '
  ([.labels[].name | select(startswith("risk:") and (startswith("risk:override-") | not))][0] // "none") as $tier
  | ([.comments[].body | capture("risk-score: scored_sha=(?<s>[0-9a-f]+)")?.s] | last // "none") as $scored
  | "pr=\(.number) state=\(.state) mergeable=\(.mergeable) merge_state=\(.mergeStateStatus) head=\(.headRefOid) branch=\(.headRefName) tier=\($tier) scored_sha=\($scored) fresh=\(if $scored == "none" then "unscored" elif $scored == .headRefOid then "yes" else "no" end) title=\(.title)"'
