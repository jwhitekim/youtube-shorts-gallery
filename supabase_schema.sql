-- Run this in Supabase Dashboard > SQL Editor

create table users (
  id               uuid primary key default gen_random_uuid(),
  google_id        text unique not null,
  email            text,
  access_token     text,
  refresh_token    text,
  token_expires_at timestamptz,
  created_at       timestamptz default now()
);

create table shorts (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references users(id) on delete cascade,
  video_id      text not null,
  title         text,
  is_short      boolean default true,
  liked_at      timestamptz,
  display_order integer,
  created_at    timestamptz default now(),
  unique(user_id, video_id)
);

-- service_role key를 사용하므로 RLS 불필요 (백엔드가 모든 접근을 중개)
