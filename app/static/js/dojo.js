/**
 * Dojo Menulis - handwriting practice page.
 * P5: free-form tracing with reference SVG + pixel-based similarity.
 * P7 later adds stroke-order verification.
 */
(function () {
  const canvas = document.getElementById('trace-canvas');
  if (!canvas) return;

  const strokes = JSON.parse(document.getElementById('stroke-data')?.textContent || '[]');
  const feedback = document.getElementById('feedback');
  const scale = canvas.width / 109;

  // Hidden canvas for reference strokes
  const refCanvas = document.createElement('canvas');
  refCanvas.width = canvas.width;
  refCanvas.height = canvas.height;
  const refCtx = refCanvas.getContext('2d');
  refCtx.scale(scale, scale);
  refCtx.strokeStyle = '#26221c'; // sumi ink (DESIGN.md)
  refCtx.lineWidth = 12;
  refCtx.lineCap = 'round';
  refCtx.lineJoin = 'round';
  strokes.forEach(function (stroke) {
    const p = new Path2D(stroke.path);
    refCtx.stroke(p);
  });

  // Drawing on visible canvas
  const ctx = canvas.getContext('2d');
  ctx.lineWidth = 14;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.strokeStyle = '#26221c';

  let drawing = false;

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches ? e.touches[0] : null;
    const clientX = touch ? touch.clientX : e.clientX;
    const clientY = touch ? touch.clientY : e.clientY;
    return {
      x: (clientX - rect.left) * (canvas.width / rect.width),
      y: (clientY - rect.top) * (canvas.height / rect.height),
    };
  }

  function start(e) {
    e.preventDefault();
    drawing = true;
    const p = getPos(e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  }

  function move(e) {
    if (!drawing) return;
    e.preventDefault();
    const p = getPos(e);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  }

  function end(e) {
    e.preventDefault();
    drawing = false;
  }

  canvas.addEventListener('mousedown', start);
  canvas.addEventListener('mousemove', move);
  canvas.addEventListener('mouseup', end);
  canvas.addEventListener('mouseleave', end);
  canvas.addEventListener('touchstart', start, { passive: false });
  canvas.addEventListener('touchmove', move, { passive: false });
  canvas.addEventListener('touchend', end, { passive: false });

  document.getElementById('btn-clear').addEventListener('click', function () {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    feedback.style.display = 'none';
  });

  function evaluateDrawing() {
    const userImg = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const refImg = refCtx.getImageData(0, 0, refCanvas.width, refCanvas.height);

    let covered = 0;
    let outside = 0;
    let uncovered = 0;
    for (let i = 3; i < refImg.data.length; i += 4) {
      const refA = refImg.data[i] > 50;
      const userA = userImg.data[i] > 50;
      if (refA && userA) covered++;
      else if (!refA && userA) outside++;
      else if (refA && !userA) uncovered++;
    }
    const total = covered + outside + uncovered;
    const accuracy = total ? covered / total : 0;
    return { accuracy, covered, outside, uncovered };
  }

  document.getElementById('btn-eval').addEventListener('click', function () {
    const score = evaluateDrawing();
    const pct = Math.round(score.accuracy * 100);
    feedback.style.display = 'block';
    if (score.accuracy >= 0.65) {
      feedback.textContent = `Bagus! ${pct}% tepat.`;
      feedback.style.cssText = 'margin-top: 12px; padding: 8px 12px; border-radius: 8px; font-size: 12px; font-weight: 700; display: block; background: var(--success-wash); color: var(--success);';
      if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playCorrect();
    } else if (score.accuracy >= 0.4) {
      feedback.textContent = `Lumayan, ${pct}%. Coba lagi!`;
      feedback.style.cssText = 'margin-top: 12px; padding: 8px 12px; border-radius: 8px; font-size: 12px; font-weight: 700; display: block; background: var(--accent-wash); color: var(--accent-dark);';
    } else {
      feedback.textContent = `Belum cukup, ${pct}%. Goreskan lebih dekat garis abu-abu.`;
      feedback.style.cssText = 'margin-top: 12px; padding: 8px 12px; border-radius: 8px; font-size: 12px; font-weight: 700; display: block; background: var(--error-wash); color: var(--error);';
      if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playWrong();
    }
  });

  // Animate reference strokes one by one
  document.getElementById('btn-animate').addEventListener('click', function () {
    const paths = document.querySelectorAll('#reference-svg .reference-stroke');
    paths.forEach(function (p, idx) {
      setTimeout(function () {
        p.setAttribute('stroke', '#c93a2e'); // vermillion accent while animating
        p.setAttribute('stroke-width', '5');
        setTimeout(function () {
          p.setAttribute('stroke', 'var(--hairline)');
          p.setAttribute('stroke-width', '3');
        }, 700);
      }, idx * 800);
    });
  });
})();
