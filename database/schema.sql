-- DROP TABLES if there are any...
-- DROP TABLE IF EXISTS student_embeddings;
-- DROP TABLE IF EXISTS student_registration;
-- DROP TABLE IF EXISTS logs;
-- DROP TABLE IF EXISTS student;
-- DROP TABLE IF EXISTS user_sessions;
-- DROP TABLE IF EXISTS users;
-- DROP TABLE IF EXISTS roles;

-- DROP TYPE and EXTENSION if there are any...
-- DROP TYPE IF EXISTS gender;
-- DROP EXTENSION IF EXISTS vector;

-- Create Gender Type as ENUM, and Vector Extension by using pgVector
-- Function is written to check whether gender exists or not since CREATE TYPE does not allow IF/IF NOT EXISTS
DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE pg_type.typname = 'gender') THEN
        CREATE TYPE gender AS ENUM('Male', 'Female');
    END IF;
END
$$;

CREATE EXTENSION IF NOT EXISTS vector;

-- Create table for role lookup (RBAC)
CREATE TABLE IF NOT EXISTS roles(
  role_name TEXT PRIMARY KEY
);

-- Create table for security users
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY,
  password_hash TEXT NOT NULL,
  role_name TEXT NOT NULL REFERENCES roles(role_name),
  totp_secret TEXT
);

-- Create table for session management
CREATE TABLE IF NOT EXISTS user_sessions (
  session_id TEXT PRIMARY KEY,
  username TEXT NOT NULL REFERENCES users(username),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL
);

-- Create table for student
CREATE TABLE IF NOT EXISTS student(
  student_id TEXT PRIMARY KEY,
  first_name TEXT NOT NULL,
  middle_name TEXT,
  last_name TEXT NOT NULL,
  gender gender NOT NULL,
  nationality TEXT NOT NULL,
  department TEXT NOT NULL DEFAULT 'No Department Assigned'
);

-- Create table for student registrations
CREATE TABLE IF NOT EXISTS student_registration (
  student_id TEXT NOT NULL REFERENCES student(student_id),
  registered_by TEXT NOT NULL REFERENCES users(username),
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(student_id)
);

-- Create table for logs
CREATE TABLE IF NOT EXISTS logs(
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMPTZ DEFAULT now(),
  event TEXT NOT NULL,
  role TEXT NOT NULL,
  logged_student_id TEXT REFERENCES student(student_id) ON DELETE SET NULL
);

-- Store Embeddings as 512-D Vectors
CREATE TABLE IF NOT EXISTS student_embeddings (
  id SERIAL PRIMARY KEY,
  student_id TEXT NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
  view_angle TEXT NOT NULL, -- 'front','left45','right45', etc...
  sample_index INTEGER NOT NULL,  -- idx: 1,2,..., 8
  student_embedding vector(512) NOT NULL,
  UNIQUE(student_id, view_angle, sample_index) -- sample_index if stored multiple from same angle
);