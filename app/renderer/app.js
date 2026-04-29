if (window._jarvisLoaded) { /* já carregado */ } else {
window._jarvisLoaded = true;

const BACKEND = 'http://localhost:8000';

let SESSION_ID = localStorage.getItem('jarvis_session_id');
if (!SESSION_ID) {
  SESSION_ID = crypto.randomUUID();
  localStorage.setItem('jarvis_session_id', SESSION_ID);
}

const chat      = document.getElementById('chat-area');
const textInput = document.getElementById('text-input');
const micBtn    = document.getElementById('mic-btn');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('file-input');

let mediaRecorder, audioChunks = [], isRecording = false;
let currentAudio = null;

// ── TTS ──────────────────────────────────────────────────────

function playAudio(b64) {
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  const audio = new Audio('data:audio/mpeg;base64,' + b64);
  currentAudio = audio;
  audio.addEventListener('play',  () => window.globe?.setState('speaking'));
  audio.addEventListener('ended', () => { window.globe?.setState('idle'); currentAudio = null; });
  audio.addEventListener('error', () => { window.globe?.setState('idle'); currentAudio = null; });
  audio.play();
}

// ── Chat UI ──────────────────────────────────────────────────

function addMessage(role, text) {
  const div = document.createElement('div');
  div.className   = `msg ${role}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop  = chat.scrollHeight;
}

// ── API ───────────────────────────────────────────────────────

async function sendText(message) {
  if (!message.trim()) return;
  addMessage('user', message);
  textInput.value = '';
  window.globe?.setState('thinking');

  try {
    const res = await fetch(`${BACKEND}/voice/speak`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: SESSION_ID }),
    });

    if (!res.ok) {
      const err = await res.text();
      console.error('[Jarvis]', res.status, err);
      addMessage('jarvis', `Erro ${res.status}: ${err.slice(0, 150)}`);
      window.globe?.setState('idle');
      return;
    }

    const data  = await res.json();
    const reply = data.reply || '';
    addMessage('jarvis', reply);
    if (data.audio_b64) playAudio(data.audio_b64);
  } catch (e) {
    console.error('[Jarvis] rede:', e);
    addMessage('jarvis', `Sem conexão com o backend: ${e.message}`);
    window.globe?.setState('idle');
  }
}

async function sendVoice(audioBlob) {
  window.globe?.setState('thinking');
  const form = new FormData();
  form.append('audio', audioBlob, 'recording.webm');
  form.append('session_id', SESSION_ID);

  try {
    const res  = await fetch(`${BACKEND}/voice/full`, { method: 'POST', body: form });
    const data = await res.json();
    if (data.user_text) addMessage('user', data.user_text);
    if (data.reply)     { addMessage('jarvis', data.reply); if (data.audio_b64) playAudio(data.audio_b64); }
  } catch (e) {
    addMessage('jarvis', 'Erro ao processar o áudio.');
    window.globe?.setState('idle');
  }
}

// ── Gravação ──────────────────────────────────────────────────

async function startRecording() {
  if (isRecording) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks  = [];
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      sendVoice(new Blob(audioChunks, { type: 'audio/webm' }));
    };
    mediaRecorder.start();
    isRecording = true;
    micBtn.classList.add('recording');
    window.globe?.setState('listening');
    if (window.streamLog) window.streamLog('MIC ATIVO');
  } catch { alert('Permita o acesso ao microfone.'); }
}

function stopRecording() {
  if (!isRecording) return;
  mediaRecorder.stop();
  isRecording = false;
  micBtn.classList.remove('recording');
}

function toggleRecording() {
  isRecording ? stopRecording() : startRecording();
}

// ── Eventos ───────────────────────────────────────────────────

textInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) sendText(textInput.value);
});

window.addEventListener('load', () => textInput.focus());
document.addEventListener('click', e => {
  if (e.target !== micBtn && e.target !== uploadBtn) textInput.focus();
});

micBtn.addEventListener('click', toggleRecording);
ipcRenderer.on('toggle-voice', toggleRecording);

uploadBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  fileInput.value = '';
  window.globe?.setState('thinking');
  addMessage('user', `Enviando exame: ${file.name}...`);
  try {
    const form = new FormData();
    form.append('file', file);
    const res  = await fetch(`${BACKEND}/health/document`, { method: 'POST', body: form });
    const data = await res.json();
    addMessage('jarvis', data.summary || 'Exame analisado.');
    if (data.audio_b64) playAudio(data.audio_b64);
  } catch {
    addMessage('jarvis', 'Erro ao analisar o exame.');
    window.globe?.setState('idle');
  }
});

} // fim do guard
