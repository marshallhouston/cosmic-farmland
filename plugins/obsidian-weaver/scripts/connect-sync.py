#!/usr/bin/env python3
"""
connect-sync.py — Incremental connection sync for Obsidian vault.

Scans modified .md files for mentions of known themes, people, concerns,
and decisions, then updates the corresponding _connections/ pages with
new source note links.

Configuration:
    OBSIDIAN_VAULT       — absolute path to your vault. Set via env var or
                           ~/.obsidian-weaver/config (written by /obsidian-setup).
                           Script exits with a structured error if neither is present.
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

import errno
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Vault location — set via OBSIDIAN_VAULT env var or ~/.obsidian-weaver/config.
CONFIG_FILE = os.path.expanduser("~/.obsidian-weaver/config")


def _resolve_vault():
    """Resolve the vault path. Emits structured error and exits 1 if missing or invalid."""
    path = os.environ.get("OBSIDIAN_VAULT", "").strip()
    if not path and os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                path = f.read().strip()
        except OSError:
            path = ""
    if not path:
        print(json.dumps({
            'status': 'error',
            'reason': 'OBSIDIAN_VAULT not set',
            'hint': 'run /obsidian-setup',
        }))
        sys.exit(1)
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        print(json.dumps({
            'status': 'error',
            'reason': 'vault not found',
            'path': path,
            'hint': 'run /obsidian-setup or fix OBSIDIAN_VAULT',
        }))
        sys.exit(1)
    return path


VAULT = _resolve_vault()
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


def atomic_write(path, data):
    """Write `data` to `path` atomically via a same-dir tempfile + os.replace."""
    dir_ = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=dir_)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _try_create_lock():
    """Atomically create LOCKFILE. Returns True on success, False if it already exists."""
    payload = json.dumps({'pid': os.getpid(), 'started': datetime.now().isoformat()})
    try:
        fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    except OSError as e:
        if e.errno == errno.EEXIST:
            return False
        raise
    with os.fdopen(fd, 'w') as f:
        f.write(payload)
    return True


def acquire_lock():
    """Try to acquire the sync lock. Returns True if acquired, False if another sync is running."""
    if _try_create_lock():
        return True
    # Existed — check staleness. One retry after unlinking a stale lock.
    try:
        lock_age = time.time() - os.path.getmtime(LOCKFILE)
    except OSError:
        return False
    if lock_age < LOCK_TTL:
        return False
    try:
        os.unlink(LOCKFILE)
    except OSError:
        pass
    return _try_create_lock()


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
    try:
        with open(REGISTRY) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(json.dumps({
            'status': 'error',
            'reason': 'registry unreadable',
            'expected_at': REGISTRY,
            'parse_error': f'{e.msg} at line {e.lineno} column {e.colno}',
            'hint': 'Fix or regenerate .registry.json — see _connections-seed/README.md for the expected shape.',
        }, indent=2))
        sys.exit(1)


def load_state():
    if not os.path.exists(STATE):
        return {'last_sync': '2020-01-01T00:00:00', 'synced_files': [], 'sync_count': 0}
    try:
        with open(STATE) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.stderr.write(
            f'warning: {STATE} is unreadable ({e.msg} at line {e.lineno}); '
            'resetting state and rescanning from scratch\n'
        )
        return {'last_sync': '2020-01-01T00:00:00', 'synced_files': [], 'sync_count': 0}


def save_state(state):
    atomic_write(STATE, json.dumps(state, indent=2))


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
    name, _ = os.path.splitext(rel)
    return name.replace(os.sep, '/')


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
        # Find next newline; if the year header is the final line (no trailing \n),
        # splice at end-of-file and ensure the year header terminates.
        next_newline = content.find('\n', idx)
        if next_newline == -1:
            if not content.endswith('\n'):
                content += '\n'
            content = content + f'- [[{note_name}]]\n'
        else:
            content = content[:next_newline + 1] + f'- [[{note_name}]]\n' + content[next_newline + 1:]
    else:
        # Add new year section at end
        content = content.rstrip() + f'\n\n{year_header}\n- [[{note_name}]]\n'

    if not dry_run:
        atomic_write(filepath, content)

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
        # Anchor only on the marker. The auto-block starts at the `## Connections`
        # header we wrote immediately above the marker; if that header is missing
        # (user hand-edited), start at the marker line itself and leave anything
        # above untouched — never hunt for a `## Connections` heading by text,
        # since the user may have authored their own elsewhere.
        marker_idx = content.index(BACKLINK_MARKER)
        line_start = content.rfind('\n', 0, marker_idx)
        line_start = 0 if line_start == -1 else line_start + 1
        auto_header = '## Connections\n'
        prev_line_start = content.rfind('\n', 0, max(line_start - 1, 0))
        prev_line_start = 0 if prev_line_start == -1 else prev_line_start + 1
        prev_line = content[prev_line_start:line_start]
        if prev_line == auto_header:
            section_start = prev_line_start
        else:
            section_start = line_start

        # End of auto-block: next `## ` header (or EOF).
        after_marker = marker_idx + len(BACKLINK_MARKER)
        next_header = content.find('\n## ', after_marker)
        section_end = len(content) if next_header == -1 else next_header + 1

        # Preserve a single newline separator before our block if we're splicing
        # mid-document so we don't collapse into the preceding paragraph.
        prefix = content[:section_start]
        suffix = content[section_end:]
        replacement = new_section.lstrip('\n')
        if prefix and not prefix.endswith('\n'):
            prefix += '\n'
        updated = prefix + replacement + suffix
    else:
        # Append new section at end
        updated = content.rstrip() + '\n' + new_section

    if updated == content:
        return False

    if not dry_run:
        atomic_write(filepath, updated)

    return True


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    if dry_run:
        args.remove('--dry-run')

    # Lock: prevent concurrent runs from multiple sessions
    if not acquire_lock():
        print(json.dumps({'status': 'error', 'reason': 'sync in progress'}))
        sys.exit(1)

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
    atomic_write(index_path, '\n'.join(lines))


if __name__ == '__main__':
    main()
