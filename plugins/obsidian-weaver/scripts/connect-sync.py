#!/usr/bin/env python3
"""
connect-sync.py — Incremental connection sync for Obsidian vault.

Scans modified .md files for mentions of known themes, people, concerns,
and decisions, then updates the corresponding _connections/ pages with
new source note links.

Configuration:
    OBSIDIAN_VAULT       — absolute path to your vault (required; defaults to ~/Documents/vault)
    OBSIDIAN_CONNECTIONS — absolute path to the connections folder (optional;
                           defaults to $OBSIDIAN_VAULT/_connections). Only set this if
                           you moved _connections/ elsewhere in your vault.

Usage:
    python3 connect-sync.py                    # Sync files modified since last run
    python3 connect-sync.py --since 2026-03-23 # Sync files modified since date
    python3 connect-sync.py --file "path.md"   # Sync a specific file
    python3 connect-sync.py --today            # Sync files modified today
    python3 connect-sync.py --dry-run          # Show what would change without writing
    python3 connect-sync.py --deep --today     # Deep mode: flag files for LLM review
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Vault location — override with OBSIDIAN_VAULT env var, or edit this path directly.
VAULT = os.environ.get("OBSIDIAN_VAULT", os.path.expanduser("~/Documents/vault"))
# Connections folder — defaults to <vault>/_connections. Override with OBSIDIAN_CONNECTIONS
# if you've moved it (must match the `connections` row in your vault's CLAUDE.md Paths table).
CONNECTIONS = os.environ.get("OBSIDIAN_CONNECTIONS", os.path.join(VAULT, "_connections"))
REGISTRY = os.path.join(CONNECTIONS, ".registry.json")
STATE = os.path.join(CONNECTIONS, ".sync-state.json")
LOCKFILE = os.path.join(CONNECTIONS, ".sync.lock")

# How long a lock is considered valid (seconds). After this, a stale lock is ignored.
LOCK_TTL = 120

# Directories to skip
SKIP_DIRS = {
    '_connections', '_templates', '.claude', '.git', '.worktrees',
    'node_modules', 'docs'
}

# Files to never inject backlinks into
SKIP_BACKLINK_FILES = {'CLAUDE.md', 'README.md', '.pr-description.md'}


def acquire_lock():
    """Try to acquire the sync lock. Returns True if acquired, False if another sync is running."""
    if os.path.exists(LOCKFILE):
        try:
            lock_age = time.time() - os.path.getmtime(LOCKFILE)
            if lock_age < LOCK_TTL:
                return False  # Another sync is actively running
            # Stale lock — previous run crashed or timed out, safe to take over
        except OSError:
            pass
    # Write lock with our PID
    with open(LOCKFILE, 'w') as f:
        f.write(json.dumps({'pid': os.getpid(), 'started': datetime.now().isoformat()}))
    return True


def release_lock():
    """Release the sync lock."""
    try:
        os.remove(LOCKFILE)
    except OSError:
        pass


def safe_connection_filename(name):
    """Sanitize a canonical entity name into a filesystem-safe filename (no extension)."""
    return name.replace('/', '-').replace(':', ' -').replace('?', '').replace('"', '')


def load_registry():
    if not os.path.exists(REGISTRY):
        print(json.dumps({
            'status': 'error',
            'reason': 'registry missing',
            'expected_at': REGISTRY,
            'hint': 'Run /obsidian-setup to seed _connections/ and create .registry.json, '
                    'or set OBSIDIAN_CONNECTIONS if your connections folder is elsewhere.',
        }, indent=2))
        sys.exit(1)
    with open(REGISTRY) as f:
        return json.load(f)


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {'last_sync': '2020-01-01T00:00:00', 'synced_files': [], 'sync_count': 0}


def save_state(state):
    with open(STATE, 'w') as f:
        json.dump(state, f, indent=2)


def find_modified_files(since_dt, specific_file=None):
    """Find .md files modified since the given datetime."""
    if specific_file:
        fp = os.path.join(VAULT, specific_file) if not os.path.isabs(specific_file) else specific_file
        if os.path.exists(fp):
            return [fp]
        return []

    modified = []
    since_ts = since_dt.timestamp()

    for root, dirs, files in os.walk(VAULT):
        # Skip excluded directories
        rel_root = os.path.relpath(root, VAULT)
        top_dir = rel_root.split(os.sep)[0]
        if top_dir in SKIP_DIRS:
            continue
        # Also filter dirs in-place to prevent descent
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for f in files:
            if not f.endswith('.md'):
                continue
            fp = os.path.join(root, f)
            if os.path.getmtime(fp) > since_ts:
                modified.append(fp)

    return sorted(modified, key=os.path.getmtime, reverse=True)


def build_matchers(registry):
    """Build regex patterns for known entities."""
    matchers = []
    alias_map = registry.get('_alias_map', {})

    # Build patterns from alias map, sorted by length (longest first for greedy matching)
    for alias, info in sorted(alias_map.items(), key=lambda x: len(x[0]), reverse=True):
        if len(alias) < 3:  # Skip very short aliases (AI, B2B, etc. - too many false positives)
            continue
        # Escape for regex, word boundary
        pattern = r'\b' + re.escape(alias) + r'\b'
        matchers.append((re.compile(pattern, re.IGNORECASE), info['type'], info['canonical']))

    return matchers


def scan_file(filepath, matchers):
    """Scan a file for entity mentions. Returns dict of {type: {canonical_name: True}}."""
    try:
        with open(filepath) as f:
            content = f.read()
    except (UnicodeDecodeError, PermissionError, FileNotFoundError):
        return {}

    # Strip auto-generated Connections section so we only match the note's real content
    marker_idx = content.find(BACKLINK_MARKER)
    if marker_idx != -1:
        section_start = content.rfind('\n## Connections', 0, marker_idx)
        if section_start == -1:
            section_start = content.rfind('## Connections', 0, marker_idx)
        else:
            section_start += 1
        after_marker = marker_idx + len(BACKLINK_MARKER)
        next_header = content.find('\n## ', after_marker)
        section_end = next_header if next_header != -1 else len(content)
        content = content[:section_start] + content[section_end:]

    content = content.lower()

    hits = defaultdict(set)
    for pattern, entity_type, canonical in matchers:
        if pattern.search(content):
            hits[entity_type].add(canonical)

    return dict(hits)


def note_name_from_path(filepath):
    """Convert filepath to Obsidian note name (without .md, relative to vault)."""
    rel = os.path.relpath(filepath, VAULT)
    return rel.replace('.md', '')


def update_connection_page(entity_type, canonical, note_name, year, dry_run=False):
    """Add a source note link to the appropriate connection page. Returns True if updated."""
    type_dir_map = {
        'theme': 'themes',
        'person': 'people',
        'concern': 'concerns',
        'decision': 'decisions',
    }
    dir_name = type_dir_map.get(entity_type)
    if not dir_name:
        return False

    filepath = os.path.join(CONNECTIONS, dir_name, safe_connection_filename(canonical) + '.md')

    if not os.path.exists(filepath):
        return False

    with open(filepath) as f:
        content = f.read()

    # Check if note is already linked
    link_pattern = f'[[{note_name}]]'
    if link_pattern in content:
        return False  # Already linked

    # Find the right year section under Source Notes
    year_header = f'### {year}'
    source_header = '## Source Notes'

    if source_header not in content:
        # Add source notes section
        content += f'\n{source_header}\n\n{year_header}\n- [[{note_name}]]\n'
    elif year_header in content:
        # Add to existing year section
        idx = content.index(year_header) + len(year_header)
        # Find next line
        next_newline = content.index('\n', idx)
        content = content[:next_newline + 1] + f'- [[{note_name}]]\n' + content[next_newline + 1:]
    else:
        # Add new year section at end
        content = content.rstrip() + f'\n\n{year_header}\n- [[{note_name}]]\n'

    if not dry_run:
        with open(filepath, 'w') as f:
            f.write(content)

    return True


BACKLINK_MARKER = '<!-- auto-generated by connect-sync — do not edit below this line -->'

TYPE_LABELS = {
    'theme': 'Themes',
    'person': 'People',
    'concern': 'Concerns',
    'decision': 'Decisions',
}


def inject_backlinks(filepath, hits, dry_run=False):
    """Write a ## Connections section into the source note with links to matched entities.
    Returns True if the file was changed."""
    if not hits:
        return False

    # Build the connections section
    section_lines = ['\n## Connections', BACKLINK_MARKER]

    for entity_type in ['theme', 'person', 'concern', 'decision']:
        names = sorted(hits.get(entity_type, set()))
        if names:
            label = TYPE_LABELS[entity_type]
            links = ', '.join(f'[[{n}]]' for n in names)
            section_lines.append(f'**{label}:** {links}')

    new_section = '\n'.join(section_lines) + '\n'

    with open(filepath) as f:
        content = f.read()

    if BACKLINK_MARKER in content:
        # Replace existing section: everything from ## Connections to end (or next ##)
        marker_idx = content.index(BACKLINK_MARKER)
        # Walk back to find the ## Connections header
        section_start = content.rfind('\n## Connections', 0, marker_idx)
        if section_start == -1:
            section_start = content.rfind('## Connections', 0, marker_idx)
        else:
            section_start += 1  # skip the leading newline

        # Find the end of the auto-generated section: next ## header or end of file
        after_marker = marker_idx + len(BACKLINK_MARKER)
        next_header = content.find('\n## ', after_marker)
        if next_header == -1:
            section_end = len(content)
        else:
            section_end = next_header

        updated = content[:section_start] + new_section.lstrip('\n') + content[section_end:]
    else:
        # Append new section at end
        updated = content.rstrip() + '\n' + new_section

    if updated == content:
        return False

    if not dry_run:
        with open(filepath, 'w') as f:
            f.write(updated)

    return True


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    if dry_run:
        args.remove('--dry-run')

    # Lock: prevent concurrent runs from multiple sessions
    if not acquire_lock():
        print(json.dumps({'status': 'skipped', 'reason': 'another sync is running'}))
        return

    try:
        _run_sync(args, dry_run)
    finally:
        release_lock()


def _run_sync(args, dry_run):
    # Determine what to sync
    state = load_state()
    registry = load_registry()
    matchers = build_matchers(registry)

    specific_file = None
    since_dt = datetime.fromisoformat(state['last_sync'])

    if '--since' in args:
        idx = args.index('--since')
        since_str = args[idx + 1]
        since_dt = datetime.fromisoformat(since_str)
    elif '--today' in args:
        since_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif '--file' in args:
        idx = args.index('--file')
        specific_file = args[idx + 1]

    # Find files
    modified = find_modified_files(since_dt, specific_file)

    if not modified:
        print(json.dumps({'status': 'no_changes', 'files_checked': 0, 'updates': []}))
        return

    # Scan and update
    updates = []
    total_links_added = 0

    for filepath in modified:
        note_name = note_name_from_path(filepath)
        basename = os.path.basename(filepath)

        # Skip if file was deleted between find and process (concurrent sessions)
        if not os.path.exists(filepath):
            continue

        # Determine year from filename or modification time
        year_match = re.match(r'(\d{4})-', basename)
        if year_match:
            year = int(year_match.group(1))
        else:
            year = datetime.fromtimestamp(os.path.getmtime(filepath)).year

        # Scan for entity mentions
        hits = scan_file(filepath, matchers)

        if not hits:
            continue

        file_updates = []
        for entity_type, names in hits.items():
            for canonical in names:
                if update_connection_page(entity_type, canonical, note_name, year, dry_run):
                    file_updates.append({'type': entity_type, 'name': canonical})
                    total_links_added += 1

        # Inject backlinks into the source note (skip config files)
        if basename not in SKIP_BACKLINK_FILES:
            inject_backlinks(filepath, hits, dry_run)

        if file_updates:
            updates.append({
                'file': basename,
                'note': note_name,
                'connections': file_updates,
            })

    # Identify files with zero or very few hits — candidates for LLM review
    # These are files the pattern matcher couldn't classify, suggesting they may
    # contain new themes/concerns/decisions not yet in the registry.
    low_hit_files = []
    for filepath in modified:
        if not os.path.exists(filepath):
            continue
        basename = os.path.basename(filepath)
        if basename in SKIP_BACKLINK_FILES:
            continue
        # Skip templates, standups dir listing, etc.
        if '/_templates/' in filepath or basename.startswith('.'):
            continue
        hits = scan_file(filepath, matchers)
        hit_count = sum(len(v) for v in hits.values())
        if hit_count <= 1:
            # Read first 200 chars to give the LLM context on what's in the file
            try:
                with open(filepath) as f:
                    preview = f.read(200).replace('\n', ' ').strip()
            except (UnicodeDecodeError, PermissionError, FileNotFoundError):
                preview = ''
            low_hit_files.append({
                'file': basename,
                'path': os.path.relpath(filepath, VAULT),
                'hits': hit_count,
                'preview': preview[:150],
            })

    # Update state
    if not dry_run:
        state['last_sync'] = datetime.now().isoformat()
        state['sync_count'] = state.get('sync_count', 0) + 1
        state['synced_files'] = [os.path.basename(f) for f in modified[:50]]
        save_state(state)

    # Rebuild index after any sync
    if not dry_run and total_links_added > 0:
        rebuild_index(registry)

    # Output report
    result = {
        'status': 'synced',
        'dry_run': dry_run,
        'files_scanned': len(modified),
        'files_with_updates': len(updates),
        'total_links_added': total_links_added,
        'updates': updates,
        'since': since_dt.isoformat(),
    }

    # Include LLM review candidates when running in deep mode
    if '--deep' in args:
        result['needs_llm_review'] = low_hit_files[:30]  # Cap at 30 to keep output manageable
        result['low_hit_total'] = len(low_hit_files)

    print(json.dumps(result, indent=2))


def rebuild_index(registry=None):
    """Rebuild _connections/_index.md from current connection pages."""
    if registry is None:
        registry = load_registry()

    lines = [
        '# Connections Index',
        '',
        f'*Auto-updated {datetime.now().strftime("%Y-%m-%d")} — '
        f'{len(registry.get("themes", []))} themes, '
        f'{len(registry.get("people", []))} people, '
        f'{len(registry.get("concerns", []))} concerns, '
        f'{len(registry.get("decisions", []))} decisions*',
        '',
    ]

    # --- Helper: parse a connection page for years and note count ---
    def parse_page_meta(filepath):
        years = set()
        note_count = 0
        try:
            with open(filepath) as f:
                content = f.read()
        except (UnicodeDecodeError, PermissionError, FileNotFoundError):
            return years, note_count
        for m in re.finditer(r'### (\d{4})', content):
            years.add(int(m.group(1)))
        note_count = content.count('[[') - content.count('[[#')  # rough count, exclude internal anchors
        return years, note_count

    # --- Themes ---
    theme_names = sorted(registry.get('themes', []))
    multi_year = []
    single_year = []
    for name in theme_names:
        path = os.path.join(CONNECTIONS, 'themes', safe_connection_filename(name) + '.md')
        years, count = parse_page_meta(path)
        entry = (name, sorted(years), count)
        if len(years) > 1:
            multi_year.append(entry)
        else:
            single_year.append(entry)

    lines.append(f'## Themes ({len(theme_names)})')
    lines.append('')
    if multi_year:
        lines.append(f'### Multi-Year ({len(multi_year)})')
        lines.append('')
        for name, years, count in multi_year:
            yr_str = ', '.join(str(y) for y in years) if years else '?'
            lines.append(f'- [[{name}]] ({yr_str}) — {count} notes')
        lines.append('')
    if single_year:
        lines.append(f'### Single-Year ({len(single_year)})')
        lines.append('')
        for name, years, count in single_year:
            yr_str = str(years[0]) if years else '?'
            lines.append(f'- [[{name}]] ({yr_str}) — {count} notes')
        lines.append('')

    # --- People (top 25 by note count) ---
    people_names = registry.get('people', [])
    people_entries = []
    for name in people_names:
        path = os.path.join(CONNECTIONS, 'people', safe_connection_filename(name) + '.md')
        years, count = parse_page_meta(path)
        people_entries.append((name, sorted(years), count))
    people_entries.sort(key=lambda x: -x[2])

    lines.append(f'## People ({len(people_entries)})')
    lines.append('')
    for name, years, count in people_entries[:25]:
        yr_str = ', '.join(str(y) for y in years) if years else '?'
        lines.append(f'- [[{name}]] ({yr_str}) — ~{count} notes')
    if len(people_entries) > 25:
        lines.append(f'- *...and {len(people_entries) - 25} more in _connections/people/*')
    lines.append('')

    # --- Concerns ---
    concern_names = sorted(registry.get('concerns', []))
    lines.append(f'## Concerns ({len(concern_names)})')
    lines.append('')
    for name in concern_names:
        path = os.path.join(CONNECTIONS, 'concerns', safe_connection_filename(name) + '.md')
        years, _ = parse_page_meta(path)
        yr_str = ', '.join(str(y) for y in sorted(years)) if years else '?'
        lines.append(f'- [[{name}]] ({yr_str})')
    lines.append('')

    # --- Decisions (grouped by year) ---
    decision_names = registry.get('decisions', [])
    decisions_by_year = defaultdict(list)
    for name in decision_names:
        path = os.path.join(CONNECTIONS, 'decisions', safe_connection_filename(name) + '.md')
        years, _ = parse_page_meta(path)
        year = min(years) if years else 0
        decisions_by_year[year].append(name)

    lines.append(f'## Decisions ({len(decision_names)})')
    lines.append('')
    for year in sorted(decisions_by_year.keys()):
        label = str(year) if year else 'Unknown'
        lines.append(f'### {label}')
        for name in sorted(decisions_by_year[year]):
            lines.append(f'- [[{name}]]')
        lines.append('')

    index_path = os.path.join(CONNECTIONS, '_index.md')
    with open(index_path, 'w') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    main()
