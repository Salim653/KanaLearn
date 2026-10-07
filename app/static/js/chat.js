/**
 * Chat simulator client logic.
 * Uses fetch for answer checking and a small canvas for handwriting placeholders.
 */
(function () {
  const app = document.getElementById('chat-app');
  if (!app) return;

  const chatId = app.dataset.chatId;
  const messagesEl = document.getElementById('messages');
  const replyDisplay = document.getElementById('reply-display');
  const feedbackEl = document.getElementById('feedback');
  const heartsEl = document.getElementById('hearts-display');
  const starsEl = document.getElementById('stars-display');
  const typingEl = document.getElementById('typing');
  const completionEl = document.getElementById('completion');
  const gameOverEl = document.getElementById('game-over');
  const keyboardPanel = document.getElementById('keyboard-panel');
  const handwritingPanel = document.getElementById('handwriting-panel');

  const stepDataRaw = document.getElementById('step-data')?.textContent;
  let currentStep = stepDataRaw && stepDataRaw !== 'null' ? JSON.parse(stepDataRaw) : null;

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showFeedback(text, type) {
    feedbackEl.textContent = text;
    feedbackEl.className =
      'quiz-feedback ' +
      (type === 'success' ? 'quiz-feedback-success' : type === 'error' ? 'quiz-feedback-error' : 'quiz-feedback-info');
    feedbackEl.style.display = 'block';
    setTimeout(() => { feedbackEl.style.display = 'none'; }, 3000);
  }

  function updateHearts(count) {
    if (!heartsEl) return;
    heartsEl.textContent = '\u2665\uFE0E ' + Math.max(0, count);
  }

  function updateStars(count) {
    if (!starsEl) return;
    starsEl.textContent = '\u2605 ' + Math.max(0, count);
  }

  function appendPlayerMessage(text, isHandwriting) {
    const wrapper = document.createElement('div');
    wrapper.className = 'chat-row chat-row-player';
    wrapper.innerHTML =
      '<div class="chat-bubble chat-bubble-player">' +
      '<p class="font-kana chat-msg-text">' + text + '</p>' +
      (isHandwriting ? '<p class="chat-msg-sub">Tulisan tangan</p>' : '') +
      '</div>';
    messagesEl.appendChild(wrapper);
    scrollToBottom();
  }

  function appendNpcMessage(msg) {
    const avatar = document.querySelector('#chat-app .chat-avatar')?.textContent?.trim() || '';
    const charName = document.querySelector('#chat-app h1')?.textContent?.trim() || '';

    const wrapper = document.createElement('div');
    wrapper.className = 'chat-row';
    wrapper.innerHTML =
      '<div class="chat-avatar-sm" aria-hidden="true">' + avatar + '</div>' +
      '<div class="chat-bubble-wrap">' +
      '<div class="chat-bubble chat-bubble-npc">' +
      '<p class="font-kana chat-msg-text chat-msg-npc">' + msg.text + '</p>' +
      (msg.romaji ? '<p class="chat-msg-sub">' + msg.romaji + '</p>' : '') +
      (msg.indonesian ? '<p class="chat-msg-sub">' + msg.indonesian + '</p>' : '') +
      '</div>' +
      (msg.is_voice_note ? '<p class="chat-msg-sub" style="margin-top: 4px;">Voice note</p>' : '') +
      '</div>';
    messagesEl.appendChild(wrapper);
    scrollToBottom();

    if (msg.is_voice_note && typeof window.KanaAudio !== 'undefined') {
      window.KanaAudio.speak(msg.text);
    }
  }

  function showTyping(cb) {
    if (!typingEl) return;
    typingEl.style.display = 'flex';
    scrollToBottom();
    setTimeout(() => {
      typingEl.style.display = 'none';
      if (cb) cb();
    }, 1200);
  }

  function handleResult(data) {
    if (data.done) {
      updateStars(data.stars);
      const finalStars = document.getElementById('final-stars');
      if (finalStars) finalStars.textContent = '\u2605 ' + data.stars;
      // Hide input area on completion
      if (keyboardPanel) keyboardPanel.style.display = 'none';
      if (handwritingPanel) handwritingPanel.style.display = 'none';
      completionEl.style.display = 'block';
      return;
    }
    if (data.game_over) {
      gameOverEl.style.display = 'block';
      return;
    }

    if (data.correct) {
      if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playCorrect();
      updateStars(data.stars);
      updateHearts(data.hearts);
      showFeedback(
        (data.handwriting_feedback ? data.handwriting_feedback + ' \u00b7 ' : '') + 'Balasan tepat!',
        'success'
      );

      appendPlayerMessage(
        currentStep.is_handwriting_challenge
          ? currentStep.handwriting_target_char
          : replyDisplay.textContent,
        currentStep.is_handwriting_challenge
      );

      // Append the next NPC message (typing indicator) then load full next-step state.
      if (data.next_message) {
        showTyping(() => {
          appendNpcMessage(data.next_message);
          loadNextStep();
        });
      } else {
        loadNextStep();
      }
    } else {
      if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playWrong();
      updateHearts(data.hearts);
      const hw = data.handwriting_feedback;
      const msg = hw
        ? hw + '. Coba ikuti garis abu-abu lebih dekat.'
        : (data.wrong_reaction || 'Belum tepat, coba lagi!');
      showFeedback(msg, 'error');
    }
  }

  // Fetch the authoritative next step (kana pool, handwriting toggle) and re-render input.
  function loadNextStep() {
    fetch('/chat/' + chatId + '/state')
      .then((r) => r.json())
      .then((st) => {
        currentStep = st.current_step;
        if (st.completed || !currentStep) return;
        renderStep(currentStep);
      })
      .catch(() => {
        // Fallback: reload to get a clean server-rendered state.
        window.location.reload();
      });
  }

  function renderStep(step) {
    replyDisplay.textContent = '';
    const isHw = step.is_handwriting_challenge;
    if (keyboardPanel) keyboardPanel.style.display = isHw ? 'none' : '';
    if (handwritingPanel) handwritingPanel.style.display = isHw ? '' : 'none';

    if (isHw) {
      refStrokes = step.handwriting_strokes || [];
      const label = handwritingPanel.querySelector('p');
      if (label) {
        label.innerHTML =
          'Goreskan huruf <span class="font-kana" style="font-size: 17px; font-weight: 800;">' +
          (step.handwriting_target_char || '') +
          '</span> mengikuti garis abu-abu:';
      }
      if (canvas && ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        refreshGuide();
      }
      return;
    }

    // Rebuild keyboard from the new pool.
    const kb = document.getElementById('keyboard');
    if (kb) {
      kb.innerHTML = '';
      (step.available_kana_pool || []).forEach((kana) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'kana-key font-kana';
        btn.textContent = kana;
        btn.addEventListener('click', () => {
          replyDisplay.textContent += kana;
          if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playKeyClick();
        });
        kb.appendChild(btn);
      });
    }
  }

  function submitReply(reply, handwritingData) {
    const formData = new FormData();
    if (reply) formData.append('reply', reply);
    if (handwritingData) formData.append('handwriting_data', handwritingData);
    formData.append('start_ms', String(Date.now()));

    fetch('/chat/' + chatId + '/submit', {
      method: 'POST',
      body: formData,
    })
      .then((r) => r.json())
      .then(handleResult)
      .catch(() => showFeedback('Gagal mengirim jawaban. Coba lagi.', 'error'));
  }

  // Keyboard input
  if (keyboardPanel && replyDisplay) {
    keyboardPanel.querySelectorAll('.kana-key').forEach((btn) => {
      btn.addEventListener('click', () => {
        replyDisplay.textContent += btn.textContent.trim();
        if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playKeyClick();
      });
    });

    document.getElementById('btn-backspace')?.addEventListener('click', () => {
      replyDisplay.textContent = replyDisplay.textContent.slice(0, -1);
      if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playKeyClick();
    });

    document.getElementById('btn-clear')?.addEventListener('click', () => {
      replyDisplay.textContent = '';
      if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playKeyClick();
    });

    document.getElementById('btn-send')?.addEventListener('click', () => {
      submitReply(replyDisplay.textContent.trim());
    });
  }

  // Handwriting canvas
  const canvas = document.getElementById('hw-canvas');
  const ctx = canvas ? canvas.getContext('2d') : null;
  let refStrokes = (currentStep && currentStep.handwriting_strokes) || [];

  // Hidden canvas that renders the reference strokes at canvas resolution.
  const refCanvas = document.createElement('canvas');
  if (canvas) {
    refCanvas.width = canvas.width;
    refCanvas.height = canvas.height;
  }

  function drawReferenceTo(c, strokes, color) {
    if (!canvas) return;
    const scale = Math.min(canvas.width, canvas.height) / 109;
    c.save();
    c.clearRect(0, 0, canvas.width, canvas.height);
    c.translate((canvas.width - 109 * scale) / 2, (canvas.height - 109 * scale) / 2);
    c.scale(scale, scale);
    c.strokeStyle = color;
    c.lineWidth = 10;
    c.lineCap = 'round';
    c.lineJoin = 'round';
    strokes.forEach(function (s) {
      const p = new Path2D(s.path);
      c.stroke(p);
    });
    c.restore();
  }

  function refreshGuide() {
    if (!canvas) return;
    // Draw the user's own canvas: faint guide underneath, user ink on top.
    const userLayer = document.createElement('canvas');
    userLayer.width = canvas.width;
    userLayer.height = canvas.height;
    userLayer.getContext('2d').drawImage(canvas, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.globalAlpha = 0.18;
    drawReferenceTo(ctx, refStrokes, '#94a3b8');
    ctx.globalAlpha = 1.0;
    ctx.drawImage(userLayer, 0, 0);
  }

  function scoreDrawing() {
    if (!canvas) return null;
    // reference mask
    const refCtx = refCanvas.getContext('2d');
    drawReferenceTo(refCtx, refStrokes, '#000000');
    const refImg = refCtx.getImageData(0, 0, refCanvas.width, refCanvas.height);
    const userImg = ctx.getImageData(0, 0, canvas.width, canvas.height);

    // user ink mask = darker than guide (guide is alpha-blended ~0.18 grey)
    let covered = 0, outside = 0, uncovered = 0;
    for (let i = 3; i < refImg.data.length; i += 4) {
      const refA = refImg.data[i] > 40;
      const ua = userImg.data[i];
      const userA = ua > 120; // user ink is dark/solid
      if (refA && userA) covered++;
      else if (!refA && userA) outside++;
      else if (refA && !userA) uncovered++;
    }
    const total = covered + outside + uncovered;
    const accuracy = total ? covered / total : 0;
    return { accuracy: accuracy * 100 };
  }

  if (canvas) {
    let drawing = false;
    ctx.lineWidth = 12;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#26221c'; // sumi ink (DESIGN.md)

    refreshGuide();

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

    document.getElementById('btn-hw-clear')?.addEventListener('click', () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      refreshGuide();
    });

    document.getElementById('btn-hw-send')?.addEventListener('click', () => {
      const score = scoreDrawing();
      const formData = new FormData();
      formData.append('handwriting_data', canvas.toDataURL('image/png'));
      if (score) formData.append('handwriting_score', String(score.accuracy.toFixed(1)));
      formData.append('start_ms', String(Date.now()));

      fetch('/chat/' + chatId + '/submit', { method: 'POST', body: formData })
        .then((r) => r.json())
        .then(handleResult)
        .catch(() => showFeedback('Gagal mengirim jawaban. Coba lagi.', 'error'));
    });
  }

  // Hint button
  document.getElementById('btn-hint')?.addEventListener('click', () => {
    fetch('/chat/' + chatId + '/hint', { method: 'POST' })
      .then((r) => r.json())
      .then((data) => {
        if (data.hint && data.hint.kana) {
          showFeedback(
            'Petunjuk: ' + data.hint.kana +
            (data.hint.romaji ? ' (' + data.hint.romaji + ')' : ''),
            'info'
          );
        }
      })
      .catch(() => showFeedback('Gagal meminta petunjuk.', 'error'));
  });

  scrollToBottom();
})();
