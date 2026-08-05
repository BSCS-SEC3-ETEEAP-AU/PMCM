// Lightweight canvas charts for the landing dashboard.
// No external chart library required.

function setupCanvas(canvas) {
  if (!canvas) return null;

  const ctx = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  const cssWidth = canvas.width;
  const cssHeight = canvas.height;

  canvas.style.width = cssWidth + 'px';
  canvas.style.height = cssHeight + 'px';
  canvas.width = Math.round(cssWidth * ratio);
  canvas.height = Math.round(cssHeight * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  return {
    ctx,
    width: cssWidth,
    height: cssHeight,
  };
}

function drawDonut(canvasId, data, options = {}) {
  const canvas = document.getElementById(canvasId);
  const setup = setupCanvas(canvas);
  if (!setup) return;

  const { ctx, width, height } = setup;
  const values = [
    Number(data.completed || 0),
    Number(data.in_progress || 0),
    Number(data.not_started || 0),
  ];
  const colors = ['#22c55e', '#3b82f6', '#9ca3af'];
  const total = values.reduce((sum, value) => sum + value, 0) || 1;

  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) / 2 - 14;
  const lineWidth = 22;
  let start = -Math.PI / 2;

  ctx.clearRect(0, 0, width, height);

  values.forEach((value, index) => {
    const angle = (value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, start, start + angle);
    ctx.strokeStyle = colors[index];
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'butt';
    ctx.stroke();
    start += angle;
  });

  ctx.beginPath();
  ctx.arc(cx, cy, radius - lineWidth / 2, 0, Math.PI * 2);
  ctx.fillStyle = '#ffffff';
  ctx.fill();

  ctx.textAlign = 'center';
  ctx.fillStyle = '#111827';
  ctx.font = '700 24px Segoe UI, sans-serif';
  ctx.fillText(options.centerText || '0%', cx, cy + 6);

  ctx.fillStyle = '#6b7280';
  ctx.font = '12px Segoe UI, sans-serif';
  ctx.fillText(options.centerSub || 'Overall Progress', cx, cy + 28);
}

function drawHBar(canvasId, rows, maxValue = 10) {
  const canvas = document.getElementById(canvasId);
  const setup = setupCanvas(canvas);
  if (!setup) return;

  const { ctx, width, height } = setup;
  const leftPad = 92;
  const rightPad = 28;
  const topPad = 18;
  const bottomPad = 26;
  const trackHeight = 18;
  const gap = 22;
  const colors = ['#9ca3af', '#3b82f6', '#f59e0b', '#22c55e'];
  const barAreaWidth = width - leftPad - rightPad;
  const safeMax = Math.max(1, Number(maxValue) || 1);

  ctx.clearRect(0, 0, width, height);
  ctx.font = '13px Segoe UI, sans-serif';
  ctx.textBaseline = 'middle';

  rows.forEach((row, index) => {
    const y = topPad + index * (trackHeight + gap);
    const value = Number(row.count || 0);
    const barWidth = Math.max(0, (value / safeMax) * barAreaWidth);

    ctx.fillStyle = '#374151';
    ctx.textAlign = 'left';
    ctx.fillText(row.label, 0, y + trackHeight / 2);

    ctx.fillStyle = '#eef2f7';
    ctx.beginPath();
    ctx.roundRect(leftPad, y, barAreaWidth, trackHeight, 8);
    ctx.fill();

    ctx.fillStyle = colors[index % colors.length];
    ctx.beginPath();
    ctx.roundRect(leftPad, y, barWidth, trackHeight, 8);
    ctx.fill();

    ctx.fillStyle = '#111827';
    ctx.textAlign = 'right';
    ctx.fillText(String(value), width, y + trackHeight / 2);
  });

  const tickCount = 4;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#6b7280';
  ctx.font = '11px Segoe UI, sans-serif';

  for (let i = 0; i <= tickCount; i += 1) {
    const value = Math.round((safeMax / tickCount) * i);
    const x = leftPad + (barAreaWidth / tickCount) * i;

    ctx.strokeStyle = '#e5e7eb';
    ctx.beginPath();
    ctx.moveTo(x, topPad - 8);
    ctx.lineTo(x, height - bottomPad + 2);
    ctx.stroke();

    ctx.fillText(String(value), x, height - 6);
  }
}

// Backward-compatible helper for the older dashboard implementation.
function drawTaskChart(canvasId, dist) {
  const rows = Object.keys(dist).map((key) => ({ label: key, count: dist[key] }));
  const maxValue = Math.max(...rows.map((row) => row.count), 10);
  drawHBar(canvasId, rows, maxValue);
}
