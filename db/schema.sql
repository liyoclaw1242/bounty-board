-- Bounty Board — Claims Database Schema
-- SQLite with WAL mode
--
-- This table is a MUTEX, not a state machine.
-- Row exists  = an agent is working on this issue.
-- Row deleted = issue is available for claiming.
-- GitHub Issues + Labels remain the source of truth for task status.

PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS claims (
    issue_number INTEGER PRIMARY KEY,          -- GitHub issue number
    agent_id     TEXT    NOT NULL,              -- e.g. "be-1700000000"
    claimed_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at   TEXT    NOT NULL,              -- TTL (default 2h from claim)
    branch_name  TEXT,                          -- e.g. "agent/be-1/issue-42"
    pr_number    INTEGER                        -- GitHub PR number once opened
);
