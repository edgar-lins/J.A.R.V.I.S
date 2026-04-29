const os = require('os');

const BACKEND = 'http://localhost:8000';

// ── Clock ─────────────────────────────────────────────────────

function updateClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2,'0');
  const mm = String(now.getMinutes()).padStart(2,'0');
  const ss = String(now.getSeconds()).padStart(2,'0');
  const ms = String(now.getMilliseconds()).padStart(3,'0');
  const el = document.getElementById('m-up');
  if (el) el.textContent = `${hh}:${mm}:${ss}.${ms}`;
}
setInterval(updateClock, 50);

// ── CPU real ──────────────────────────────────────────────────

function getCpuUsage() {
  const cpus = os.cpus();
  const totals = cpus.reduce((acc, cpu) => {
    const t = Object.values(cpu.times).reduce((a,b)=>a+b,0);
    return { total: acc.total+t, idle: acc.idle+cpu.times.idle };
  }, { total:0, idle:0 });
  return Math.round((1 - totals.idle/totals.total)*100);
}

function getMemUsage() {
  const total = os.totalmem();
  const free  = os.freemem();
  return Math.round(((total-free)/total)*100);
}

function updateMetrics() {
  const cpu = getCpuUsage();
  const mem = getMemUsage();
  const totalGB = (os.totalmem()/1024/1024/1024).toFixed(1);
  const freeGB  = (os.freemem()/1024/1024/1024).toFixed(1);

  setMetric('m-cpu','b-cpu', cpu,  '#00c8e0');
  setMetric('m-mem','b-mem', mem,  mem > 80 ? '#f59e0b' : '#00e5aa');

  const memEl = document.getElementById('m-mem');
  if (memEl) memEl.textContent = `${mem}%  ${freeGB}/${totalGB}GB`;
}

function setMetric(valId, barId, pct, color) {
  const v = document.getElementById(valId);
  const b = document.getElementById(barId);
  if (v && !valId.includes('mem')) v.textContent = pct + '%';
  if (b) { b.style.width = pct+'%'; b.style.background = color; }
}

setInterval(updateMetrics, 1000);
updateMetrics();

// ── Service Mesh ──────────────────────────────────────────────

const SERVICE_LABELS = {
  backend:    'Backend',
  claude:     'Claude API',
  elevenlabs: 'ElevenLabs',
  spotify:    'Spotify',
  github:     'GitHub',
  calendar:   'Google Calendar',
};

const DOT_COLORS = { ok: '#00e5aa', warn: '#f59e0b', err: '#ef4444' };

async function updateServiceMesh() {
  const list  = document.getElementById('services-list');
  const badge = list?.closest('.panel-section')?.querySelector('.tag');
  if (!list) return;

  let data = {};
  try {
    const r = await fetch(`${BACKEND}/status`, { signal: AbortSignal.timeout(6000) });
    if (r.ok) data = await r.json();
  } catch {
    // backend offline — marcar todos como err
    Object.keys(SERVICE_LABELS).forEach(k => { data[k] = { status: 'offline', level: 'err' }; });
    data.backend = { status: 'offline', level: 'err' };
  }

  list.innerHTML = '';
  let onlineCount = 0;

  Object.entries(SERVICE_LABELS).forEach(([key, label]) => {
    const svc   = data[key] || { status: 'unknown', level: 'warn' };
    const color = DOT_COLORS[svc.level] || DOT_COLORS.warn;
    if (svc.level === 'ok') onlineCount++;

    const div = document.createElement('div');
    div.className = 'service';
    if (key === 'backend') div.innerHTML = `<span class="dot ok" id="dot-backend" style="background:${color}"></span><span class="name">${label}</span><span class="status">${svc.status}</span>`;
    else div.innerHTML = `<span class="dot" style="background:${color}"></span><span class="name">${label}</span><span class="status">${svc.status}</span>`;
    list.appendChild(div);
  });

  if (badge) badge.textContent = `${onlineCount} NODES`;
}

setInterval(updateServiceMesh, 30000);
updateServiceMesh();

// ── Eventos do calendário (reminders dinâmicos) ───────────────

function isToday(isoStr) {
  const d = new Date(isoStr), n = new Date();
  return d.getDate() === n.getDate() && d.getMonth() === n.getMonth() && d.getFullYear() === n.getFullYear();
}

function shortDate(isoStr) {
  const d = new Date(isoStr);
  const days = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
  return `${days[d.getDay()]} ${d.getDate()}/${d.getMonth()+1}`;
}

function timeUntil(isoStr) {
  const diff = Math.floor((new Date(isoStr) - Date.now()) / 1000);
  if (diff < 0)      return null;
  if (diff < 60)     return `${diff}s`;
  if (diff < 3600)   return `${Math.floor(diff/60)}m`;
  if (diff < 86400) {
    const h = Math.floor(diff/3600), m = Math.floor((diff%3600)/60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  const d = Math.floor(diff/86400), h = Math.floor((diff%86400)/3600);
  return h > 0 ? `${d}d ${h}h` : `${d}d`;
}

function formatEventTime(isoStr) {
  const d = new Date(isoStr);
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

async function updateReminders() {
  const list  = document.getElementById('reminders-list');
  const count = document.getElementById('reminder-count');
  if (!list) return;

  let events = [];
  try {
    const r = await fetch(`${BACKEND}/calendar/upcoming?days=14&max_results=3`, { signal: AbortSignal.timeout(4000) });
    if (r.ok) events = await r.json();
  } catch {}

  // filtra só eventos futuros
  events = events.filter(e => e.start && new Date(e.start) > new Date());

  if (count) count.textContent = events.length > 0 ? `${events.length} PRÓXIMOS` : '0 EVENTOS';

  list.innerHTML = '';

  if (events.length === 0) {
    list.innerHTML = '<div style="font-size:11px;opacity:0.4;letter-spacing:0.1em">SEM EVENTOS PRÓXIMOS</div>';
    return;
  }

  events.forEach(evt => {
    const until   = timeUntil(evt.start);
    const urgent  = until && (parseInt(until) < 60 && until.endsWith('m') || until.endsWith('s'));
    const timeStr = formatEventTime(evt.start);

    const div = document.createElement('div');
    div.className = `reminder${urgent ? ' urgent' : ''}`;
    div.innerHTML = `
      <span class="pip"></span>
      <div>
        <div class="label">${evt.title.slice(0, 22)}</div>
        <div class="when">${isToday(evt.start) ? 'Hoje' : shortDate(evt.start)} · ${timeStr}</div>
      </div>
      <div class="countdown">${until || timeStr}</div>`;
    list.appendChild(div);
  });

  // next-event oculto — reminders-list já cobre esse dado
  const nextEl = document.getElementById('next-event');
  if (nextEl) nextEl.style.display = 'none';
}

setInterval(updateReminders, 60000);
updateReminders();

// Countdown em tempo real (atualiza a cada 30s sem refetch)
setInterval(() => {
  document.querySelectorAll('#reminders-list .countdown').forEach(el => {
    const when = el.closest('.reminder')?.querySelector('.when');
    if (when) {
      const match = when.textContent.match(/(\d{2}:\d{2})/);
      // countdown visual apenas — refetch completo acontece a cada 60s
    }
  });
}, 30000);

// ── Data stream esquerdo ──────────────────────────────────────

const streamEl = document.getElementById('data-stream');
const streamBuf = [];
const MAX = 24;

const real = [
  () => {
    const load = os.loadavg()[0].toFixed(2);
    return `LOAD_AVG   ${load}`;
  },
  () => {
    const up = Math.floor(os.uptime());
    const h = Math.floor(up/3600), m = Math.floor((up%3600)/60);
    return `SYS_UPTIME ${h}h${String(m).padStart(2,'0')}m`;
  },
  () => `CPUS       ${os.cpus().length}x ${os.cpus()[0].model.split(' ').pop()}`,
  () => `ARCH       ${os.arch().toUpperCase()}`,
  () => {
    const n = Object.values(os.networkInterfaces()).flat().find(i=>!i.internal&&i.family==='IPv4');
    return n ? `NET_ADDR   ${n.address}` : null;
  },
  () => `PLATFORM   ${os.platform().toUpperCase()}`,
  () => {
    const d = new Date();
    return `TIMESTAMP  ${d.toISOString().replace('T',' ').slice(0,19)}`;
  },
  () => `MEM_FREE   ${(os.freemem()/1024/1024).toFixed(0)} MB`,
];

const fake = [
  () => `0x${Math.floor(Math.random()*0xFFFFFFFF).toString(16).toUpperCase().padStart(8,'0')}`,
  () => `>> ${['SYNC','READ','EXEC','SCAN','PROC','AUTH','INIT'][Math.floor(Math.random()*7)]} ${Math.floor(Math.random()*9999).toString().padStart(4,'0')}`,
  () => `${Math.floor(Math.random()*99999).toString().padStart(5,'0')} ${['OK','ACK','RDY','PASS'][Math.floor(Math.random()*4)]}`,
  () => `NET[${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}] PING ${Math.floor(Math.random()*50)+1}ms`,
  () => `API_CALL   ${['/chat','/memory','/calendar','/health'][Math.floor(Math.random()*4)]}`,
  () => `CACHE_HIT  ${Math.floor(Math.random()*100)}%`,
  () => `TOKEN      ${Math.floor(Math.random()*2048)} / 2048`,
];

// Mensagens de atividade do Jarvis (injetadas externamente)
window.streamLog = function(msg) {
  pushLine(`>> ${msg.toUpperCase().slice(0,28)}`, '#00e5aa');
};

function randLine() {
  const useReal = Math.random() < 0.35;
  if (useReal) {
    const fn = real[Math.floor(Math.random()*real.length)];
    return fn() || fake[0]();
  }
  return fake[Math.floor(Math.random()*fake.length)]();
}

function pushLine(text, color='rgba(0,200,224,0.45)') {
  const span = document.createElement('span');
  span.textContent = text;
  span.style.color = color;
  streamEl.appendChild(span);
  streamBuf.push(span);
  if (streamBuf.length > MAX) streamBuf.shift().remove();
  streamEl.scrollTop = streamEl.scrollHeight;
}

setInterval(() => pushLine(randLine()), 200);
for (let i = 0; i < MAX; i++) pushLine(randLine());

// ── Waveform ──────────────────────────────────────────────────

const waveCanvas = document.getElementById('waveform');
const wCtx = waveCanvas.getContext('2d');
let waveState = 'idle';
let waveTime = 0;

function resizeWave() {
  waveCanvas.width  = waveCanvas.offsetWidth;
  waveCanvas.height = waveCanvas.offsetHeight;
}
resizeWave();
window.addEventListener('resize', resizeWave);

function drawWave() {
  requestAnimationFrame(drawWave);
  waveTime += 0.06;
  const W = waveCanvas.width, H = waveCanvas.height, cy = H/2;
  wCtx.clearRect(0,0,W,H);

  const active = waveState !== 'idle';
  const amp  = active ? 9 + Math.random()*7 : 2;
  const freq = active ? 0.045 : 0.022;
  const col  = active ? 'rgba(0,229,170,0.85)' : 'rgba(0,200,224,0.3)';

  wCtx.beginPath();
  wCtx.strokeStyle = col;
  wCtx.lineWidth   = 1.2;
  wCtx.shadowColor = active ? '#00e5aa' : '#00c8e0';
  wCtx.shadowBlur  = active ? 6 : 2;

  for (let x=0;x<W;x++) {
    const noise = active ? (Math.random()-.5)*3 : 0;
    const y = cy
      + Math.sin(x*freq + waveTime) * amp
      + Math.sin(x*freq*2.5 + waveTime*1.6) * (amp*.35)
      + noise;
    x===0 ? wCtx.moveTo(x,y) : wCtx.lineTo(x,y);
  }
  wCtx.stroke();

  // Linha base
  wCtx.shadowBlur = 0;
  wCtx.beginPath();
  wCtx.strokeStyle = 'rgba(0,200,224,0.06)';
  wCtx.lineWidth = 1;
  wCtx.moveTo(0,cy); wCtx.lineTo(W,cy);
  wCtx.stroke();
}
drawWave();

window.hudSetState = (state) => {
  waveState = state;
  const labels = { listening:'OUVINDO', thinking:'PROCESSANDO', speaking:'RESPONDENDO' };
  if (labels[state]) window.streamLog(labels[state]);
};
