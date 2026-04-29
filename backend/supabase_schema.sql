-- ============================================================
-- JARVIS — Schema do Supabase
-- Execute este SQL no SQL Editor do seu projeto Supabase
-- ============================================================

-- Extensão para UUID
create extension if not exists "uuid-ossp";

-- ------------------------------------------------------------
-- Perfil pessoal do usuário
-- ------------------------------------------------------------
create table if not exists profiles (
    id           uuid primary key default uuid_generate_v4(),
    user_id      text unique not null,
    name         text,
    age          int,
    height_cm    numeric(5,2),
    weight_kg    numeric(5,2),
    occupation   text,
    goals        text[],          -- ex: ['perder peso', 'crescer na carreira']
    preferences  jsonb default '{}',
    created_at   timestamptz default now(),
    updated_at   timestamptz default now()
);

-- ------------------------------------------------------------
-- Memórias de longo prazo (fatos sobre o usuário)
-- ------------------------------------------------------------
create table if not exists memories (
    id          uuid primary key default uuid_generate_v4(),
    user_id     text not null references profiles(user_id) on delete cascade,
    category    text not null,  -- 'health' | 'work' | 'personal' | 'preference' | 'routine'
    content     text not null,
    importance  int default 1 check (importance between 1 and 5),
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

create index if not exists memories_user_category on memories(user_id, category);

-- ------------------------------------------------------------
-- Histórico de conversas
-- ------------------------------------------------------------
create table if not exists conversations (
    id          uuid primary key default uuid_generate_v4(),
    user_id     text not null references profiles(user_id) on delete cascade,
    session_id  text not null,
    role        text not null check (role in ('user', 'assistant')),
    content     text not null,
    created_at  timestamptz default now()
);

create index if not exists conversations_session on conversations(session_id, created_at);

-- ------------------------------------------------------------
-- Dados de saúde (série temporal)
-- ------------------------------------------------------------
create table if not exists health_data (
    id          uuid primary key default uuid_generate_v4(),
    user_id     text not null references profiles(user_id) on delete cascade,
    metric      text not null,   -- 'weight_kg' | 'blood_pressure' | 'sleep_hours' | etc.
    value       numeric(10,4) not null,
    unit        text,
    notes       text,
    recorded_at timestamptz default now()
);

create index if not exists health_data_user_metric on health_data(user_id, metric, recorded_at desc);

-- ------------------------------------------------------------
-- Exames e documentos de saúde
-- ------------------------------------------------------------
create table if not exists health_documents (
    id              uuid primary key default uuid_generate_v4(),
    user_id         text not null references profiles(user_id) on delete cascade,
    filename        text not null,
    file_path       text not null,   -- path no Supabase Storage
    document_type   text,            -- 'blood_test' | 'xray' | 'prescription' | etc.
    summary         text,            -- resumo extraído pelo Jarvis
    raw_text        text,            -- texto extraído do PDF/imagem
    uploaded_at     timestamptz default now()
);

-- ------------------------------------------------------------
-- Rotina e hábitos
-- ------------------------------------------------------------
create table if not exists routines (
    id          uuid primary key default uuid_generate_v4(),
    user_id     text not null references profiles(user_id) on delete cascade,
    name        text not null,       -- 'Treino A', 'Rotina Matinal', etc.
    type        text not null,       -- 'workout' | 'diet' | 'habit' | 'schedule'
    content     jsonb not null,      -- estrutura da rotina
    active      boolean default true,
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

-- ------------------------------------------------------------
-- Trigger: atualizar updated_at automaticamente
-- ------------------------------------------------------------
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger profiles_updated_at before update on profiles
    for each row execute function update_updated_at();

create trigger memories_updated_at before update on memories
    for each row execute function update_updated_at();

create trigger routines_updated_at before update on routines
    for each row execute function update_updated_at();
