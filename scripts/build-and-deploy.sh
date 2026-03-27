#!/usr/bin/env bash
#
# Daily build-and-deploy script for Langsame Nachrichten.
# Runs the content pipeline, assembles the site with a 3-day rolling archive,
# and force-pushes to the gh-pages branch for GitHub Pages deployment.
#
# Usage:
#   ./scripts/build-and-deploy.sh
#
# Required environment:
#   OPENAI_API_KEY    — OpenAI API key for LLM calls
#   TTS_BACKEND       — "qwen" for free local TTS, "openai" for API (default: openai)
#
# Optional:
#   VENV_PATH         — Path to Python venv (default: .venv)
#   KEEP_DAYS         — Number of days to keep in archive (default: 3)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
KEEP_DAYS="${KEEP_DAYS:-3}"
VENV_PATH="${VENV_PATH:-.venv}"
GHPAGES_DIR="$PROJECT_DIR/.ghpages-worktree"
LOG_FILE="$PROJECT_DIR/build.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

die() {
    log "ERROR: $*"
    exit 1
}

cd "$PROJECT_DIR"

log "=== Starting build-and-deploy ==="

# --- Validate environment ---
if [ -z "${OPENAI_API_KEY:-}" ]; then
    die "OPENAI_API_KEY is not set"
fi

if [ ! -d "$VENV_PATH" ]; then
    die "Python venv not found at $VENV_PATH"
fi

# --- Activate venv ---
# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"

# --- Step 1: Run the content pipeline ---
log "Running content pipeline (TTS_BACKEND=${TTS_BACKEND:-openai})..."
python -m backend.build || die "Pipeline failed"
log "Pipeline complete."

# --- Step 2: Build Tailwind CSS ---
log "Building Tailwind CSS..."
if command -v npx &>/dev/null; then
    npx @tailwindcss/cli -i frontend/input.css -o frontend/styles.css --minify 2>/dev/null
    log "Tailwind CSS built."
else
    if [ -f frontend/styles.css ]; then
        log "WARNING: npx not found, using existing styles.css"
    else
        die "npx not found and no existing styles.css — cannot build site"
    fi
fi

# --- Step 3: Set up gh-pages worktree ---
# Ensure the gh-pages branch exists (create orphan if not)
if ! git show-ref --verify --quiet refs/heads/gh-pages 2>/dev/null; then
    log "Creating orphan gh-pages branch..."
    git checkout --orphan gh-pages
    git rm -rf . 2>/dev/null || true
    git commit --allow-empty -m "Initial gh-pages branch"
    git checkout -
fi

# Set up or update the worktree
if [ ! -d "$GHPAGES_DIR" ]; then
    log "Creating gh-pages worktree at $GHPAGES_DIR..."
    git worktree add "$GHPAGES_DIR" gh-pages
else
    log "Updating gh-pages worktree..."
    (cd "$GHPAGES_DIR" && git checkout gh-pages && git reset --hard HEAD)
fi

# --- Step 4: Assemble site into worktree ---
log "Assembling site..."

# Copy frontend files (minus source CSS)
for f in frontend/*; do
    fname="$(basename "$f")"
    [ "$fname" = "input.css" ] && continue
    cp -r "$f" "$GHPAGES_DIR/"
done

# Copy today's content
TODAY=$(date +%Y-%m-%d)
TODAY_CONTENT="output/content/$TODAY"
if [ ! -d "$TODAY_CONTENT" ]; then
    die "No content generated for today ($TODAY)"
fi

mkdir -p "$GHPAGES_DIR/content/$TODAY"
cp -r "$TODAY_CONTENT"/* "$GHPAGES_DIR/content/$TODAY/"

# Copy today's digest as latest.json
if [ -f "$TODAY_CONTENT/digest.json" ]; then
    cp "$TODAY_CONTENT/digest.json" "$GHPAGES_DIR/content/latest.json"
fi

# --- Step 5: Prune old content (keep last KEEP_DAYS days) ---
log "Pruning content older than $KEEP_DAYS days..."
if [ -d "$GHPAGES_DIR/content" ]; then
    # List date directories, sort, and remove all but the most recent KEEP_DAYS
    # shellcheck disable=SC2012
    DATES=$(ls -d "$GHPAGES_DIR/content"/????-??-??/ 2>/dev/null | sort -r)
    COUNT=0
    for dir in $DATES; do
        COUNT=$((COUNT + 1))
        if [ "$COUNT" -gt "$KEEP_DAYS" ]; then
            log "  Removing old content: $(basename "$dir")"
            rm -rf "$dir"
        fi
    done
fi

# --- Step 6: Generate archive.json ---
log "Generating archive.json..."
ARCHIVE_DATES=""
# shellcheck disable=SC2012
for dir in $(ls -d "$GHPAGES_DIR/content"/????-??-??/ 2>/dev/null | sort -r); do
    DATE_STR=$(basename "$dir")
    if [ -n "$ARCHIVE_DATES" ]; then
        ARCHIVE_DATES="$ARCHIVE_DATES, \"$DATE_STR\""
    else
        ARCHIVE_DATES="\"$DATE_STR\""
    fi
done
echo "{\"dates\": [$ARCHIVE_DATES]}" > "$GHPAGES_DIR/content/archive.json"
log "  Dates in archive: $ARCHIVE_DATES"

# --- Step 7: Commit and push ---
log "Committing and pushing to gh-pages..."
cd "$GHPAGES_DIR"

# Safety: never push to main
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    die "SAFETY: Refusing to push to $CURRENT_BRANCH"
fi

git add -A
if git diff --cached --quiet; then
    log "No changes to deploy."
else
    git commit -m "Deploy: $TODAY"
    git push origin gh-pages --force
    log "Deployed successfully!"
fi

cd "$PROJECT_DIR"

# --- Step 8: Prune local output for disk hygiene ---
log "Pruning local output..."
if [ -d "output/content" ]; then
    LOCAL_COUNT=0
    # shellcheck disable=SC2012
    for dir in $(ls -d output/content/????-??-??/ 2>/dev/null | sort -r); do
        LOCAL_COUNT=$((LOCAL_COUNT + 1))
        if [ "$LOCAL_COUNT" -gt "$KEEP_DAYS" ]; then
            log "  Removing local: $(basename "$dir")"
            rm -rf "$dir"
        fi
    done
fi

log "=== Build-and-deploy complete ==="
