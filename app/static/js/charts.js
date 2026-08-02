// Lightweight canvas charting (no external deps) for thesis dashboards.
function drawTaskChart(canvasId, dist) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const labels = Object.keys(dist);
  const values = Object.values(dist);
  const max = Math.max(1, ...values);
  const colors = ['#94a3b8', '#60a5fa', '#34d399', '#fbbf24', '#a78bfa'];
  const W = canvas.width, H = canvas.height;
  const pad = 30, barW = (W - pad * 2) / labels.length - 10;
  ctx.clearRect(0, 0, W, H);
  ctx.font = '11px sans-serif';
  let x = pad;
  values.forEach((v, i) => {
    const h = (v / max) * (H - pad * 2);
    ctx.fillStyle = colors[i % colors.length];
    ctx.fillRect(x, H - pad - h, barW, h);
    ctx.fillStyle = '#334155';
    ctx.fillText(String(v), x + barW / 2 - 4, H - pad - h - 5);
    ctx.save();
    ctx.translate(x + barW / 2, H - pad + 12);
    ctx.rotate(-Math.PI / 6);
    ctx.fillText(labels[i], 0, 0);
    ctx.restore();
    x += barW + 10;
  });
  ctx.strokeStyle = '#cbd5e1';
  ctx.beginPath(); ctx.moveTo(pad, H - pad); ctx.lineTo(W - pad, H - pad); ctx.stroke();
}
