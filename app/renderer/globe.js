class JarvisVisualizer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.canvas = document.createElement('canvas');
    this.canvas.style.cssText = 'display:block;width:100%;height:100%';
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    this.state = 'idle';
    this.time = 0;
    this.angles = Array(8).fill(0);
    this._resize();
    window.addEventListener('resize', () => this._resize());
    this._animate();
  }

  _resize() {
    const r = this.container.getBoundingClientRect();
    this.canvas.width  = r.width;
    this.canvas.height = r.height;
    this.cx = r.width  / 2;
    this.cy = r.height / 2;
    this.R  = Math.min(r.width, r.height) * 0.44;
  }

  setState(state) {
    if (this.state === state) return;
    this.state = state;
    const labels = { idle:'ONLINE', listening:'OUVINDO', thinking:'PROCESSANDO', speaking:'RESPONDENDO' };
    const el = document.getElementById('status-label');
    if (el) { el.textContent = labels[state]||state; el.className = state!=='idle'?'active':''; }
    if (window.hudSetState) window.hudSetState(state);
  }

  // ── Helpers ──────────────────────────────────────────────────

  _ring(r, {color='#00c8e0', opacity=0.5, lw=1, dash=[], ticks=0, tickLen=6, angle=0, arc=1}={}) {
    const ctx = this.ctx;
    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.strokeStyle = color;
    ctx.lineWidth   = lw;
    ctx.shadowColor = color;
    ctx.shadowBlur  = lw > 1.5 ? 8 : 4;
    ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.arc(this.cx, this.cy, r, angle, angle + Math.PI * 2 * arc);
    ctx.stroke();
    ctx.setLineDash([]);

    if (ticks > 0) {
      ctx.lineWidth = 0.8;
      ctx.shadowBlur = 2;
      for (let i = 0; i < ticks; i++) {
        const a = angle + (i / ticks) * Math.PI * 2;
        const isMajor = i % (ticks / 4) === 0;
        const tl = isMajor ? tickLen * 1.8 : tickLen;
        ctx.globalAlpha = isMajor ? opacity : opacity * 0.5;
        ctx.beginPath();
        ctx.moveTo(this.cx + Math.cos(a) * (r - tl/2), this.cy + Math.sin(a) * (r - tl/2));
        ctx.lineTo(this.cx + Math.cos(a) * (r + tl/2), this.cy + Math.sin(a) * (r + tl/2));
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  _glow(r, color, strength) {
    const ctx = this.ctx;
    const g = ctx.createRadialGradient(this.cx, this.cy, 0, this.cx, this.cy, r);
    g.addColorStop(0,   color.replace('1)', `${strength})`));
    g.addColorStop(0.35,color.replace('1)', `${strength*0.4})`));
    g.addColorStop(0.7, color.replace('1)', `${strength*0.1})`));
    g.addColorStop(1,   color.replace('1)', '0)'));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(this.cx, this.cy, r, 0, Math.PI*2);
    ctx.fill();
  }

  _segmentedRing(r, segments, gapDeg, {color, opacity, lw, angle=0}={}) {
    const gap = (gapDeg * Math.PI) / 180;
    const arc = (Math.PI * 2 - segments * gap) / segments;
    for (let i = 0; i < segments; i++) {
      const start = angle + i * (arc + gap);
      this._ring(r, { color, opacity, lw, arc: arc / (Math.PI*2), angle: start });
    }
  }

  // ── Animate ──────────────────────────────────────────────────

  _animate() {
    requestAnimationFrame(() => this._animate());
    this.time += 0.016;

    const active  = this.state !== 'idle';
    const mul     = active ? 2.4 : 1.0;
    const breathe = Math.sin(this.time * (active ? 2.8 : 0.75)) * 0.5 + 0.5;

    // Rotações individuais
    this.angles[0] += 0.0018 * mul;
    this.angles[1] -= 0.003  * mul;
    this.angles[2] += 0.005  * mul;
    this.angles[3] -= 0.007  * mul;
    this.angles[4] += 0.011  * mul;
    this.angles[5] -= 0.014  * mul;
    this.angles[6] += 0.020  * mul;
    this.angles[7] -= 0.025  * mul;

    const ctx = this.ctx;
    const W = this.canvas.width, H = this.canvas.height;
    ctx.clearRect(0, 0, W, H);

    const R  = this.R;
    const C  = '#00c8e0';
    const C2 = '#00e5aa';
    const b  = breathe;

    // ── Glow ambiente ──
    this._glow(R * 0.7, 'rgba(0,150,220,1)', 0.12 + b*0.06);
    this._glow(R * 0.35,'rgba(0,200,255,1)', 0.25 + b*0.1);

    // ── Anel externo com ticks ──
    this._ring(R,       { color:C,  opacity:0.25+b*0.08, lw:1,   ticks:72, tickLen:5,  angle:this.angles[0] });

    // ── Segmentado (blocos) ──
    this._segmentedRing(R*0.92, 24, 2, { color:C,  opacity:0.5, lw:2, angle:this.angles[1] });

    // ── Anel tracejado rápido ──
    this._ring(R*0.82,  { color:C2, opacity:0.4+b*0.1, lw:1,   dash:[3,5], angle:this.angles[2] });

    // ── Anel sólido médio ──
    this._ring(R*0.72,  { color:C,  opacity:0.55+b*0.1, lw:2,   ticks:36, tickLen:7, angle:this.angles[3] });

    // ── Segmentado interior ──
    this._segmentedRing(R*0.61, 12, 3, { color:C2, opacity:0.5+b*0.15, lw:2.5, angle:this.angles[4] });

    // ── Anel pontilhado fino ──
    this._ring(R*0.50,  { color:C,  opacity:0.5, lw:1, dash:[2,4], angle:this.angles[5] });

    // ── Anel interno brilhante ──
    this._ring(R*0.38,  { color:C2, opacity:0.65+b*0.2, lw:2.5, ticks:24, tickLen:6, angle:this.angles[6] });

    // ── Anel mais interno ──
    this._segmentedRing(R*0.26, 8, 4, { color:C, opacity:0.7+b*0.2, lw:2, angle:this.angles[7] });

    // ── Core glow ──
    const cr = 18 + b*10 + (active ? 8 : 0);
    this._glow(cr*4,    'rgba(0,220,255,1)', 0.35 + b*0.15);
    this._glow(cr*1.5,  'rgba(255,255,255,1)', 0.6 + b*0.2);

    // Ponto branco central
    ctx.save();
    ctx.fillStyle = `rgba(255,255,255,${0.85+b*0.15})`;
    ctx.shadowColor = '#00d4ff';
    ctx.shadowBlur  = 20;
    ctx.beginPath();
    ctx.arc(this.cx, this.cy, cr*0.35, 0, Math.PI*2);
    ctx.fill();
    ctx.restore();

    // ── Texto J.A.R.V.I.S ──
    const fs = Math.floor(R * 0.095);
    ctx.save();
    ctx.font         = `${fs}px 'Share Tech Mono', monospace`;
    ctx.fillStyle    = `rgba(0,200,224,${0.65+b*0.25})`;
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor  = '#00c8e0';
    ctx.shadowBlur   = 12;
    ctx.fillText('J.A.R.V.I.S', this.cx, this.cy);
    ctx.restore();

    // Sub-texto estado (quando ativo)
    if (active) {
      const sub = { listening:'OUVINDO', thinking:'PROCESSANDO', speaking:'RESPONDENDO' }[this.state] || '';
      ctx.save();
      ctx.font         = `${Math.floor(R*0.055)}px 'Share Tech Mono', monospace`;
      ctx.fillStyle    = `rgba(0,229,170,${0.5+b*0.4})`;
      ctx.textAlign    = 'center';
      ctx.textBaseline = 'middle';
      ctx.shadowColor  = '#00e5aa';
      ctx.shadowBlur   = 8;
      ctx.fillText(sub, this.cx, this.cy + R*0.16);
      ctx.restore();
    }
  }
}

window.globe = new JarvisVisualizer('globe-container');
