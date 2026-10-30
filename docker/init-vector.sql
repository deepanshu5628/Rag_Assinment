-- Runs once on first container init (empty data dir).
-- PGEngine.init_vectorstore_table also runs CREATE EXTENSION IF NOT EXISTS vector,
-- this is belt-and-suspenders so the extension exists from the very first boot.
CREATE EXTENSION IF NOT EXISTS vector;
