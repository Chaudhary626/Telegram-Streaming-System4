-- Telegram Video Streaming System — MySQL schema
-- Charset utf8mb4 for full unicode support.
SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE DATABASE IF NOT EXISTS telegram_stream
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE telegram_stream;

-- ---------- plans ----------
CREATE TABLE IF NOT EXISTS plans (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(64) NOT NULL UNIQUE,
  price         INT NOT NULL DEFAULT 0,
  duration_days INT NOT NULL DEFAULT 30,
  max_videos    INT NOT NULL DEFAULT 0,
  features      TEXT NULL,
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- users ----------
CREATE TABLE IF NOT EXISTS users (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  username        VARCHAR(64) NOT NULL UNIQUE,
  password_hash   VARCHAR(255) NOT NULL,
  role            ENUM('admin','subadmin') NOT NULL DEFAULT 'subadmin',
  telegram_id     BIGINT NULL UNIQUE,
  is_active       TINYINT(1) NOT NULL DEFAULT 1,
  plan_id         INT NULL,
  plan_expires_at DATETIME NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_users_plan FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- contents (hierarchical) ----------
CREATE TABLE IF NOT EXISTS contents (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  owner_id    INT NOT NULL,
  parent_id   INT NULL,
  title       VARCHAR(255) NOT NULL,
  slug        VARCHAR(255) NOT NULL,
  type        ENUM('movie','series','season','episode') NOT NULL DEFAULT 'movie',
  description TEXT NULL,
  poster_url  VARCHAR(512) NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_owner_slug (owner_id, slug),
  KEY idx_contents_parent (parent_id),
  CONSTRAINT fk_contents_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_contents_parent FOREIGN KEY (parent_id) REFERENCES contents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- video_sources ----------
CREATE TABLE IF NOT EXISTS video_sources (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  content_id     INT NOT NULL,
  channel_id     BIGINT NOT NULL,
  message_id     BIGINT NOT NULL,
  file_id        VARCHAR(255) NOT NULL,
  file_unique_id VARCHAR(128) NOT NULL,
  file_size      BIGINT NOT NULL DEFAULT 0,
  file_name      VARCHAR(512) NULL,
  mime_type      VARCHAR(128) NULL,
  language       VARCHAR(32) NOT NULL DEFAULT 'original',
  quality        VARCHAR(16) NOT NULL DEFAULT 'auto',
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_sources_content (content_id),
  CONSTRAINT fk_sources_content FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- payment_methods ----------
CREATE TABLE IF NOT EXISTS payment_methods (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  name         VARCHAR(64) NOT NULL,
  type         VARCHAR(32) NOT NULL,
  details      TEXT NULL,
  instructions TEXT NULL,
  is_active    TINYINT(1) NOT NULL DEFAULT 1,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- payment_requests ----------
CREATE TABLE IF NOT EXISTS payment_requests (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL,
  plan_id         INT NOT NULL,
  method_id       INT NULL,
  amount          INT NOT NULL DEFAULT 0,
  transaction_ref VARCHAR(128) NULL,
  proof_file_id   VARCHAR(255) NULL,
  status          ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  admin_note      TEXT NULL,
  reviewed_at     DATETIME NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_payments_user (user_id),
  KEY idx_payments_status (status),
  CONSTRAINT fk_payments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_payments_plan FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE RESTRICT,
  CONSTRAINT fk_payments_method FOREIGN KEY (method_id) REFERENCES payment_methods(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- audit_logs ----------
CREATE TABLE IF NOT EXISTS audit_logs (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  actor_id   INT NULL,
  action     VARCHAR(128) NOT NULL,
  detail     TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_audit_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- seed default plans ----------
INSERT INTO plans (name, price, duration_days, max_videos, features, is_active)
VALUES
  ('Free',    0,    36500, 5,    'Basic playback', 1),
  ('Basic',   199,  30,    50,   'More videos, embed', 1),
  ('Pro',     499,  30,    500,  'Multi-quality, multi-audio, ads', 1),
  ('Premium', 999,  30,    0,    'Unlimited videos, all features', 1)
ON DUPLICATE KEY UPDATE name = VALUES(name);
