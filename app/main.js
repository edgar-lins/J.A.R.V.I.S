const { app, BrowserWindow, ipcMain, globalShortcut } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let mainWindow;
let backendProcess = null;

const BACKEND_DIR    = path.join(__dirname, '..', 'backend');
const PYTHON_BIN     = path.join(BACKEND_DIR, 'venv', 'bin', 'python');
const BACKEND_SCRIPT = path.join(BACKEND_DIR, 'main.py');
const BACKEND_URL    = 'http://localhost:8000/health';

// ── Backend ───────────────────────────────────────────────────

function startBackend() {
  console.log('[Jarvis] Iniciando backend...');

  backendProcess = spawn(PYTHON_BIN, [BACKEND_SCRIPT], {
    cwd: BACKEND_DIR,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  });

  backendProcess.stdout.on('data', d => process.stdout.write(`[Backend] ${d}`));
  backendProcess.stderr.on('data', d => process.stderr.write(`[Backend] ${d}`));

  backendProcess.on('exit', (code) => {
    console.log(`[Jarvis] Backend encerrado (código ${code})`);
    backendProcess = null;
  });
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Jarvis] Encerrando backend...');
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
}

function waitForBackend(retries = 20, delay = 500) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      http.get(BACKEND_URL, (res) => {
        if (res.statusCode === 200) resolve();
        else retry(n);
      }).on('error', () => retry(n));
    };

    const retry = (n) => {
      if (n <= 0) return reject(new Error('Backend não respondeu a tempo.'));
      setTimeout(() => attempt(n - 1), delay);
    };

    attempt(retries);
  });
}

// ── Window ────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 820,
    height: 900,
    minWidth: 600,
    minHeight: 700,
    frame: false,
    transparent: false,
    backgroundColor: '#000000',
    titleBarStyle: 'hidden',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false,
    },
  });

  mainWindow.loadFile('renderer/index.html');
  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── App lifecycle ─────────────────────────────────────────────

app.whenReady().then(async () => {
  startBackend();

  try {
    console.log('[Jarvis] Aguardando backend subir...');
    await waitForBackend();
    console.log('[Jarvis] Backend pronto.');
  } catch (e) {
    console.error('[Jarvis] Backend demorou demais — abrindo mesmo assim.');
  }

  createWindow();

  // Cmd+Shift+J — mostra/esconde o app
  globalShortcut.register('CommandOrControl+Shift+J', () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    }
  });

  // Cmd+Option+J — ativa/para gravação de voz de qualquer lugar
  const voiceShortcut = 'CommandOrControl+Alt+J';
  const voiceOk = globalShortcut.register(voiceShortcut, () => {
    if (mainWindow) {
      if (!mainWindow.isVisible()) mainWindow.show();
      mainWindow.webContents.send('toggle-voice');
    }
  });
  console.log(`[Jarvis] Atalho de voz (${voiceShortcut}):`, voiceOk ? 'OK' : 'FALHOU — já em uso');
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (!mainWindow) createWindow();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  stopBackend();
});

// IPC
ipcMain.on('window-close',   () => mainWindow?.close());
ipcMain.on('window-minimize',() => mainWindow?.minimize());
