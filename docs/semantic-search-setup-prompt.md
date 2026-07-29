# Prompt: add local semantic search to a Bible-text directory

Paste everything below into a fresh Claude Code session opened in the **new** directory
that holds the Bible text. Leave it as-is.

---

I want local, offline semantic search over the Bible text in this directory.
No cloud, no API keys, no resident daemon.

## Reference implementation

`~/code/lennys-newsletterpodcastdata-all/bin/lenny-semantic.py` is a proven local-semantic-search
script. **Read it first.** Reuse its entire architecture; only
the chunking and reference-labeling change for Bible text. Write the adapted script at
`bin/semantic.py` in THIS directory.

Architecture to keep verbatim:
- Embeddings run in **Ollama** (Metal-accelerated Go binary); Python speaks HTTP to it via
  **stdlib only** — no pip, no numpy, no sentence-transformers (local Python may be 3.14,
  no PyTorch wheels).
- Ollama daemon started **only while a command runs**, stopped on exit unless `--keep`.
  `serve` / `stop` subcommands for manual warm querying. Nothing left resident.
- Store: SQLite, vectors as packed `<Nf` float BLOBs, cosine in pure stdlib. The whole
  index is read into memory per command (cursor scan over all chunks) — no resident cache.
- **Delta-aware** index: sha1 each source file, skip unchanged, re-embed only what changed.
- Model `nomic-embed-text` with task prefixes — `search_document: ` on index,
  `search_query: ` on query. Env: `BIBLE_EMBED_MODEL` (the reference uses `LENNY_EMBED_MODEL`;
  rename it for this tool), `OLLAMA_HOST`.
- DB at `.semantic/vec.db`; add `.semantic/` to `.gitignore`.

### Schema change (required — three commands below depend on it)
The reference `chunks` table is `(id, file, ord, heading, text, vec)` with no scripture
columns. **Extend it** so aggregation and reference-lookup have something to key on:
```sql
ALTER ... -- add to the chunks table:
book TEXT, chapter INT, verse_start INT, verse_end INT
-- and: CREATE INDEX idx_chunks_ref ON chunks(book, chapter);
```
Without these columns, `--by-chapter`, `--by-book`, and `like "<ref>"` cannot be built.

## STEP 1 — inspect the data before writing any chunker

I don't yet know the file layout (per-book, per-chapter, or one big file) or the text
format (plain text, Markdown, USFM, OSIS, per-verse lines, "1:1 ..." prefixes, etc.).

Do this first and report back:
1. `ls` the directory tree; count source files; show the paths.
2. Show the first ~40 lines of 2–3 representative files.
3. Tell me: one file per book? per chapter? one big file? And how are book / chapter /
   verse boundaries marked in the raw text?

Then propose a parser that extracts a `(book, chapter, verse, text)` stream from whatever
format this is. **Confirm the parse with me before indexing** — show ~5 parsed verses with
their refs so I can verify book/chapter/verse detection is correct.

## STEP 2 — chunking (verse-grouped)

Replace the reference script's markdown-heading chunker with a verse-grouped chunker:
- Group **consecutive verses up to ~1500 chars**, but **never cross a chapter boundary** —
  a chunk stays within one book+chapter.
- Hard-split any single verse longer than the cap on a sentence/whitespace boundary.
- Each chunk carries metadata: `book`, `chapter`, `verse_start`, `verse_end`.
- The text embedded for a chunk should lead with a human reference line
  (e.g. `Genesis 1:1-5`) then the verse text, so the reference is part of the signal.

## STEP 3 — commands + output

- `index [--keep]` — delta-aware build/refresh.
- `query "<text>" [-n N] [--by-book] [--by-chapter] [--keep]` — passages by meaning.
  - Default: top-N verse-group hits, each printed as `score  Book chap:Vstart-Vend  « snippet »`.
  - `--by-chapter`: aggregate to the best hit per chapter.
  - `--by-book`: aggregate to the best hit per book.
- `like "<Book Chap:Verse>"` (or a book name) — passages whose centroid is closest to the
  given reference's verses. "More like this." **Note:** the reference script resolves `like`
  by a *file-name slug* (`file LIKE %slug%`) — that does NOT transfer. Resolve the input
  against the new scripture columns instead:
  - `like "John 3:16"` → `SELECT vec FROM chunks WHERE book='John' AND chapter=3
    AND verse_start<=16 AND verse_end>=16`
  - `like "John"` → `WHERE book='John'`
  Centroid those vectors, search, exclude the source ref's own chunks from results.
- `serve` / `stop` — daemon lifecycle. **Caveat:** the reference `stop` is a blunt
  `pkill -f "ollama serve"` — it kills *every* Ollama daemon, including one the user started
  outside this tool. Keep that behavior but document it in CLAUDE.md.

Citations everywhere should be `Book Chapter:Verse[-Verse]`, NOT file paths.

## Prereqs — check, don't assume

Run and report missing pieces before writing code:
- `which ollama` (else `brew install ollama`)
- `ollama list | grep nomic-embed-text` (else `ollama pull nomic-embed-text`)
- `python3 --version` (stdlib only)

## After building

1. Build: `bin/semantic.py index`. Report verse count + chunk count.
2. Run smoke tests and show top 5 hits with refs:
   - `query "love your enemies"`
   - `query "the beginning of creation" --by-book`
3. Spot-check: do the returned refs actually contain the matching text? Read the cited
   verses and confirm.
4. Add a `## Semantic search` section to this dir's CLAUDE.md (create if absent): the three
   commands, the `Book chap:verse` citation convention, and that `.semantic/vec.db` is a
   gitignored, rebuildable sidecar — never commit it.

Don't index until Step 1's parse is confirmed by me.
