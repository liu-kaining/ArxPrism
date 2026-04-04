-- ArxPrism Supabase 初始化脚本（粘贴到 Supabase SQL Editor）
-- 依赖：已有 auth.users

-- ---------------------------------------------------------------------------
-- profiles：与 auth.users 1:1，角色 / 配额 / 封禁
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role text not null default 'user' check (role in ('user', 'admin')),
  quota_limit int not null default 10 check (quota_limit >= 0),
  quota_used int not null default 0 check (quota_used >= 0),
  is_banned boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists profiles_role_idx on public.profiles (role);

-- ---------------------------------------------------------------------------
-- system_settings：单行配置（Worker / API 通过 service role 读取）
-- ---------------------------------------------------------------------------
create table if not exists public.system_settings (
  id int primary key default 1 check (id = 1),
  triage_threshold double precision not null default 0.5
    check (triage_threshold >= 0 and triage_threshold <= 1),
  html_first_enabled boolean not null default true,
  updated_at timestamptz not null default now()
);

insert into public.system_settings (id, triage_threshold, html_first_enabled)
values (1, 0.5, true)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- 新用户自动建 profile
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, role, quota_limit, quota_used, is_banned)
  values (new.id, 'user', 10, 0, false)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- updated_at 维护
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_updated_at on public.profiles;
create trigger profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

drop trigger if exists system_settings_updated_at on public.system_settings;
create trigger system_settings_updated_at
  before update on public.system_settings
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Quota RPC（security definer，仅 service role / 服务端调用）
-- ---------------------------------------------------------------------------
create or replace function public.try_consume_task_quota(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  lim int;
  used int;
  banned boolean;
begin
  select p.quota_limit, p.quota_used, p.is_banned
    into lim, used, banned
  from public.profiles p
  where p.id = p_user_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'reason', 'no_profile');
  end if;

  if banned then
    return jsonb_build_object('ok', false, 'reason', 'banned');
  end if;

  if used >= lim then
    return jsonb_build_object('ok', false, 'reason', 'quota_exhausted');
  end if;

  update public.profiles
  set quota_used = quota_used + 1
  where id = p_user_id;

  return jsonb_build_object('ok', true);
end;
$$;

create or replace function public.refund_task_quota(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.profiles
  set quota_used = greatest(0, quota_used - 1)
  where id = p_user_id;
end;
$$;

grant usage on schema public to anon, authenticated, service_role;
grant select, insert, update on public.profiles to service_role;
grant select, update on public.system_settings to service_role;
grant execute on function public.try_consume_task_quota(uuid) to service_role;
grant execute on function public.refund_task_quota(uuid) to service_role;

-- ---------------------------------------------------------------------------
-- RLS（建议）：客户端直连 PostgREST 时；本后端主要用 service role 可绕过 RLS
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.system_settings enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);

drop policy if exists "system_settings_select_authenticated" on public.system_settings;
create policy "system_settings_select_authenticated"
  on public.system_settings for select
  to authenticated
  using (true);

-- 首个管理员：在 Supabase SQL Editor 执行（将 uuid 换成你的 auth.users.id）
-- update public.profiles set role = 'admin' where id = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx';
