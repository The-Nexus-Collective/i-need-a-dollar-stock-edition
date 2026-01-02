#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# AI-Powered Git Commit Script
# Stages all changes, generates a commit message using AI, commits, and pushes
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
# Load .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check for API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}Error: OPENAI_API_KEY not set${NC}"
    echo "Please set OPENAI_API_KEY in your environment or .env file"
    exit 1
fi

# ─── FUNCTIONS ─────────────────────────────────────────────────────────────────

check_dependencies() {
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}Error: curl is required but not installed${NC}"
        exit 1
    fi
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}Error: jq is required but not installed${NC}"
        echo "Install with: brew install jq"
        exit 1
    fi
}

check_git_repo() {
    if ! git rev-parse --is-inside-work-tree &> /dev/null; then
        echo -e "${RED}Error: Not a git repository${NC}"
        exit 1
    fi
}

check_changes() {
    if [ -z "$(git status --porcelain)" ]; then
        echo -e "${YELLOW}No changes to commit${NC}"
        exit 0
    fi
}

stage_changes() {
    echo -e "${BLUE}→ Staging all changes...${NC}"
    git add -A
    echo -e "${GREEN}✓ Changes staged${NC}"
}

get_diff() {
    git diff --staged --no-color
}

get_changed_files() {
    git diff --staged --name-only
}

generate_commit_message() {
    local diff="$1"
    local files="$2"
    
    # Truncate diff if too long (max ~4000 chars for API)
    if [ ${#diff} -gt 4000 ]; then
        diff="${diff:0:4000}...(truncated)"
    fi
    
    echo -e "${BLUE}→ Generating commit message with AI...${NC}"
    
    # Escape special characters for JSON
    local escaped_diff=$(echo "$diff" | jq -Rs .)
    local escaped_files=$(echo "$files" | jq -Rs .)
    
    local prompt="You are a git commit message generator. Analyze the following git diff and generate a concise, conventional commit message.

Rules:
1. Use conventional commit format: type(scope): description
2. Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
3. Scope is optional but recommended (e.g., api, ui, auth)
4. Description should be imperative mood, lowercase, no period
5. Keep the first line under 72 characters
6. If there are multiple significant changes, add a body with bullet points
7. Only output the commit message, nothing else

Changed files:
$files

Git diff:
$diff"

    local json_payload=$(jq -n \
        --arg model "gpt-4o-mini" \
        --arg prompt "$prompt" \
        '{
            model: $model,
            messages: [
                {role: "system", content: "You are a helpful assistant that generates git commit messages."},
                {role: "user", content: $prompt}
            ],
            max_tokens: 200,
            temperature: 0.3
        }')
    
    local response=$(curl -s https://api.openai.com/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $OPENAI_API_KEY" \
        -d "$json_payload")
    
    # Check for errors
    local error=$(echo "$response" | jq -r '.error.message // empty')
    if [ -n "$error" ]; then
        echo -e "${RED}API Error: $error${NC}"
        return 1
    fi
    
    # Extract the commit message
    local message=$(echo "$response" | jq -r '.choices[0].message.content // empty')
    
    if [ -z "$message" ]; then
        echo -e "${RED}Failed to generate commit message${NC}"
        return 1
    fi
    
    echo "$message"
}

manual_commit() {
    echo -e "${YELLOW}Falling back to manual commit...${NC}"
    echo -n "Enter commit message: "
    read -r message
    if [ -z "$message" ]; then
        echo -e "${RED}Commit aborted: empty message${NC}"
        exit 1
    fi
    echo "$message"
}

confirm_and_commit() {
    local message="$1"
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}Generated Commit Message:${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}$message${NC}"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    echo -n -e "${YELLOW}Proceed with commit and push? [Y/n/e(dit)]: ${NC}"
    read -r confirm
    
    case "$confirm" in
        n|N|no|No|NO)
            echo -e "${RED}Commit aborted${NC}"
            git reset HEAD -- . &> /dev/null
            exit 0
            ;;
        e|E|edit|Edit|EDIT)
            echo "Enter new commit message (Ctrl+D when done):"
            message=$(cat)
            if [ -z "$message" ]; then
                echo -e "${RED}Commit aborted: empty message${NC}"
                git reset HEAD -- . &> /dev/null
                exit 1
            fi
            ;;
        *)
            # Proceed with commit
            ;;
    esac
    
    echo -e "${BLUE}→ Committing...${NC}"
    git commit -m "$message"
    echo -e "${GREEN}✓ Committed${NC}"
    
    echo -e "${BLUE}→ Pushing to remote...${NC}"
    local branch=$(git branch --show-current)
    git push origin "$branch"
    echo -e "${GREEN}✓ Pushed to origin/$branch${NC}"
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ All done!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
}

# ─── MAIN ──────────────────────────────────────────────────────────────────────

main() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║            AI-Powered Git Commit                              ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    check_dependencies
    check_git_repo
    check_changes
    stage_changes
    
    local diff=$(get_diff)
    local files=$(get_changed_files)
    
    echo -e "${BLUE}Changed files:${NC}"
    echo "$files" | while read -r file; do
        echo -e "  ${YELLOW}•${NC} $file"
    done
    echo ""
    
    local commit_message
    if commit_message=$(generate_commit_message "$diff" "$files"); then
        confirm_and_commit "$commit_message"
    else
        commit_message=$(manual_commit)
        confirm_and_commit "$commit_message"
    fi
}

main "$@"

