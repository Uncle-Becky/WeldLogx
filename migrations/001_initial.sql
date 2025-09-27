PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS welders (
    welder_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS seams (
    seam_id TEXT PRIMARY KEY,
    description TEXT,
    customer TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS segments (
    seam_id TEXT NOT NULL,
    segment_no INTEGER NOT NULL,
    start_in REAL NOT NULL,
    end_in REAL NOT NULL,
    pass_list TEXT NOT NULL,
    segment_status TEXT NOT NULL DEFAULT 'Not started',
    percent_complete REAL NOT NULL DEFAULT 0.0,
    root_by TEXT,
    root_at TEXT,
    fill_by TEXT,
    fill_at TEXT,
    cap_by TEXT,
    cap_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (seam_id, segment_no),
    FOREIGN KEY (seam_id) REFERENCES seams(seam_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    seam_id TEXT NOT NULL,
    segment_no INTEGER NOT NULL,
    pass TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('Start', 'Complete')),
    welder_id TEXT NOT NULL,
    shift TEXT CHECK(shift IN ('Day', 'Night', 'Swing') OR shift IS NULL),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (seam_id, segment_no) REFERENCES segments(seam_id, segment_no) ON DELETE CASCADE,
    FOREIGN KEY (welder_id) REFERENCES welders(welder_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_entries_lookup
    ON entries(seam_id, segment_no, pass, action, timestamp);
CREATE INDEX IF NOT EXISTS idx_entries_welder
    ON entries(welder_id);
CREATE INDEX IF NOT EXISTS idx_segments_seam
    ON segments(seam_id);
