-- Bounty Board — Database Schema
-- SQLite with WAL mode

PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

-- Registered target repos
CREATE TABLE IF NOT EXISTS repos (
    slug          TEXT PRIMARY KEY,       -- "owner/repo"
    github_token  TEXT NOT NULL,
    repo_dir      TEXT NOT NULL,          -- local path to cloned repo
    bot_username  TEXT DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Claim mutex (prevents two agents from working on the same issue)
-- Row exists = agent is working. Row deleted = available.
CREATE TABLE IF NOT EXISTS claims (
    repo_slug    TEXT    NOT NULL,
    issue_number INTEGER NOT NULL,
    agent_id     TEXT    NOT NULL,
    claimed_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at   TEXT    NOT NULL,
    branch_name  TEXT,
    pr_number    INTEGER,
    PRIMARY KEY (repo_slug, issue_number),
    FOREIGN KEY (repo_slug) REFERENCES repos(slug) ON DELETE CASCADE
);
