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
