# J.A.R.V.I.S

> Just A Rather Very Intelligent System — assistente pessoal com IA, voz e interface HUD.

![Jarvis HUD](../../../Desktop/jarvis.png)

---

## Visão geral

Jarvis é um assistente pessoal de IA inspirado no filme Iron Man, rodando 100% local no Mac. Você fala, ele escuta, age e responde com voz. Conecta com sua agenda, e-mail, GitHub, Spotify e muito mais — tudo por voz ou pelo chat da interface.

**Arquitetura:**
- `backend/` — API Python (FastAPI) com toda a lógica de IA, integrações e voz
- `app/` — Interface Electron com HUD estilo Iron Man (Three.js + WebGL)

---

## Funcionalidades

### Voz
- **Wake word** — diz "Jarvis" para ativar (detecção local via Whisper, sem internet)
- **Modo sessão** — após ativar, fica ouvindo por 60s sem precisar repetir "Jarvis"
- **TTS** — respostas em voz com ElevenLabs (fallback para macOS `say`)
- **STT** — transcrição local via faster-whisper

### IA
- Powered by **Claude** (Anthropic) com agentic loop — executa ações reais
- Memória de longo prazo via **Supabase** (perfil, memórias, rotinas, saúde)
- Data e hora injetadas no contexto — nunca agenda no ano errado

### Integrações
| Serviço | Capacidades |
|---|---|
| **Google Calendar** | Criar, editar, deletar e listar eventos por voz |
| **Gmail** | Ler, marcar como lido/não lido, responder e-mails |
| **GitHub** | PRs, issues, notificações, detalhes de pull requests |
| **Spotify** | Tocar, pausar, próxima, anterior, volume, o que está tocando |
| **Brave Search** | Busca web em tempo real — placares, notícias, preços |
| **Clima** | Temperatura, condição e previsão do dia (wttr.in) |

### Proativo
- Briefing matinal com agenda e GitHub (voz + notificação)
- Alerta de reuniões 30 minutos antes
- Check de PRs e menções no GitHub durante horário de trabalho
- Resumo noturno às 22h

### Mac Agent
- Abrir apps, controlar browser, executar comandos no terminal
- Screenshot com análise visual — "Jarvis, o que tá errado aqui?"
- Clipboard, volume, notificações nativas, travar tela

### Lembretes
- "Jarvis, me lembra daqui 20 minutos de ligar pro médico"
- "Jarvis, me lembra às 15h da reunião"
- Fala em voz alta quando dispara

---

## Stack

**Backend**
- Python 3.12
- FastAPI + Uvicorn
- Anthropic SDK (Claude Opus)
- faster-whisper (STT local)
- ElevenLabs SDK (TTS)
- Supabase (memória)
- APScheduler (proativo)
- Spotipy, PyGithub, google-api-python-client

**Frontend**
- Electron 33
- Three.js (globo 3D)
- HTML/CSS/JS puro

---

## Pré-requisitos

- macOS (testado no macOS 15+)
- Python 3.12
- Node.js 18+
- Conta no [Supabase](https://supabase.com) (gratuito)
- API key da [Anthropic](https://console.anthropic.com)
- API key da [ElevenLabs](https://elevenlabs.io) (opcional)
- API key da [Brave Search](https://api.search.brave.com) (opcional)

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/jarvis-os.git
cd jarvis-os
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copie o arquivo de exemplo e preencha as variáveis:

```bash
cp .env.example .env
```

| Variável | Onde obter |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `SUPABASE_URL` + `SUPABASE_KEY` + `SUPABASE_SERVICE_KEY` | Projeto no [supabase.com](https://supabase.com) |
| `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` | [elevenlabs.io](https://elevenlabs.io) |
| `BRAVE_API_KEY` | [api.search.brave.com](https://api.search.brave.com) |
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → Classic token |
| `GITHUB_USERNAME` | Seu usuário do GitHub |
| `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET` | [developer.spotify.com](https://developer.spotify.com) |

Inicialize o banco de dados no Supabase executando o SQL em `backend/supabase_schema.sql`.

### 3. Frontend

```bash
cd ../app
npm install
```

---

## Configurações opcionais

### Google Calendar / Gmail

```bash
cd backend
# Siga as instruções em: https://console.cloud.google.com
# Baixe as credenciais OAuth como google_credentials.json
python -c "from integrations.google_calendar import get_auth_url; print(get_auth_url())"
# Ou acesse http://localhost:8000/auth/google após iniciar o backend
```

### Spotify

```bash
cd backend
python scripts/spotify_auth.py
```

No dashboard do Spotify, adicione `https://open.spotify.com` como Redirect URI.

---

## Rodando

```bash
cd app
npm start
```

O app inicia o backend Python automaticamente e abre a interface HUD.

**Atalhos:**
| Atalho | Ação |
|---|---|
| `Cmd+Shift+J` | Mostrar / esconder a janela |
| `Cmd+Option+J` | Ativar gravação de voz |

---

## Estrutura do projeto

```
jarvis-os/
├── backend/
│   ├── api/              # Rotas FastAPI
│   ├── core/             # Brain (IA), memória, scheduler, proativo
│   ├── integrations/     # Google Calendar, Gmail, GitHub, Spotify, Brave
│   ├── mac_agent/        # Controle do macOS via AppleScript
│   ├── voice/            # Wake word, STT, TTS
│   ├── health/           # Análise de exames médicos
│   ├── scripts/          # Utilitários (auth Spotify, etc.)
│   ├── main.py           # Entry point do servidor
│   ├── config.py         # Configurações via .env
│   └── requirements.txt
└── app/
    ├── main.js           # Entry point Electron
    └── renderer/
        ├── index.html    # HUD principal
        ├── app.js        # Lógica de chat e voz
        ├── hud.js        # Métricas, clock, serviços, reminders
        └── globe.js      # Globo 3D (Three.js)
```

---

## Licença

MIT
