CREATE TABLE IF NOT EXISTS published_topics (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  topic_hash TEXT UNIQUE,
  category TEXT,
  status TEXT DEFAULT 'draft',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY,
  topic_id INTEGER REFERENCES published_topics(id),
  body TEXT NOT NULL,
  image_path TEXT,
  image_prompt TEXT,
  status TEXT DEFAULT 'pending',
  admin_feedback TEXT,
  regen_count INTEGER DEFAULT 0,
  length_hint TEXT,
  message_id INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  published_at TEXT
);

CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY,
  chat_id INTEGER,
  message_id INTEGER,
  user_id INTEGER,
  username TEXT,
  text TEXT,
  status TEXT DEFAULT 'new',
  classification TEXT,
  bot_reply TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  processed_at TEXT,
  UNIQUE(chat_id, message_id)
);

CREATE TABLE IF NOT EXISTS ai_logs (
  id INTEGER PRIMARY KEY,
  kind TEXT,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  images INTEGER DEFAULT 0,
  est_cost_usd REAL,
  created_at TEXT DEFAULT (datetime('now'))
);


CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS story_jobs (
  id INTEGER PRIMARY KEY,
  target TEXT NOT NULL,
  theme INTEGER,
  prompt_en TEXT,
  image_path TEXT,
  caption TEXT,
  status TEXT DEFAULT 'pending',
  feedback TEXT,
  regen_count INTEGER DEFAULT 0,
  message_id INTEGER,
  story_msg_id INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  publish_at TEXT
);

CREATE TABLE IF NOT EXISTS saga_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  episode_number INTEGER DEFAULT 0,
  arc_number INTEGER DEFAULT 1,
  arc_goal TEXT,
  arc_plan_json TEXT DEFAULT '[]',
  planned_arc_length INTEGER DEFAULT 6,
  episode_in_arc INTEGER DEFAULT 0,
  harmon_stage TEXT DEFAULT '1-Ты',
  characters_json TEXT DEFAULT '{}',
  locations_json TEXT DEFAULT '[]',
  last_summary TEXT,
  prev_message_id INTEGER,
  narration TEXT,
  pending_arc_seed TEXT,
  arc_status TEXT DEFAULT 'in_progress',
  arc_synopsis_json TEXT DEFAULT '[]',
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS saga_summaries (
  id INTEGER PRIMARY KEY,
  episode_number INTEGER NOT NULL,
  arc_number INTEGER NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);
