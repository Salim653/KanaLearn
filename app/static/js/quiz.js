/**
 * Quiz lesson runner - vanilla JS island.
 * Renders one question at a time, checks answer client-side, then POSTs outcomes.
 * Styling follows the washi & ink design system (DESIGN.md) via app.css classes.
 */
(function () {
  const app = document.getElementById('quiz-app');
  if (!app) return;

  const lessonId = app.dataset.lessonId;
  const promptArea = document.getElementById('prompt-area');
  const optionsArea = document.getElementById('options-area');
  const tilesArea = document.getElementById('tiles-area');
  const answerDisplay = document.getElementById('answer-display');
  const feedbackArea = document.getElementById('feedback-area');
  const heartsDisplay = document.getElementById('hearts-display');
  const progressDisplay = document.getElementById('progress-display');
  const submitBtn = document.getElementById('btn-submit');
  const nextBtn = document.getElementById('btn-next');
  const listenBtn = document.getElementById('btn-listen');
  const endScreen = document.getElementById('end-screen');
  const endAccuracy = document.getElementById('end-accuracy');
  const endXp = document.getElementById('end-xp');

  let questions = [];
  let currentIndex = 0;
  let selected = null;
  let builtAnswer = '';
  let hearts = 5;
  let heartsEnabled = true;
  let outcomes = [];
  let answered = false;
  let reviewQueue = [];   // indices of questions answered wrong, to re-ask at the end
  let inReview = false;
  let reviewAttempts = 0;

  function setHearts(n) {
    hearts = Math.max(0, n);
    if (!heartsEnabled) return;
    heartsDisplay.textContent = '\u2665\uFE0E ' + hearts; // text heart, ink-colored via CSS
  }

  function showFeedback(text, type) {
    feedbackArea.textContent = text;
    feedbackArea.className =
      'quiz-feedback ' +
      (type === 'success' ? 'quiz-feedback-success' : type === 'error' ? 'quiz-feedback-error' : 'quiz-feedback-info');
    feedbackArea.style.display = 'block';
  }

  function speakCurrent() {
    const q = questions[currentIndex];
    if (q && q.tts_text && typeof window.KanaAudio !== 'undefined') {
      window.KanaAudio.speak(q.tts_text);
    }
  }

  function clearSelected() {
    Array.from(optionsArea.children).forEach((b) => b.classList.remove('quiz-option-selected'));
  }

  function renderMcq(q) {
    selected = null;
    optionsArea.style.display = 'grid';
    tilesArea.style.display = 'none';
    answerDisplay.textContent = '';
    optionsArea.innerHTML = '';
    q.options.forEach((opt) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'quiz-option';
      btn.textContent = opt;
      btn.addEventListener('click', () => {
        selected = opt;
        clearSelected();
        btn.classList.add('quiz-option-selected');
      });
      optionsArea.appendChild(btn);
    });
  }

  function renderTiles(q) {
    selected = null;
    optionsArea.style.display = 'none';
    tilesArea.style.display = 'flex';
    answerDisplay.textContent = '';
    tilesArea.innerHTML = '';
    builtAnswer = '';
    q.tiles.forEach((tile) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'quiz-tile';
      btn.textContent = tile;
      btn.addEventListener('click', () => {
        builtAnswer += tile;
        answerDisplay.textContent = builtAnswer;
      });
      tilesArea.appendChild(btn);
    });
    const reset = document.createElement('button');
    reset.type = 'button';
    reset.className = 'btn btn-ghost btn-sm';
    reset.textContent = 'Reset';
    reset.addEventListener('click', () => {
      builtAnswer = '';
      answerDisplay.textContent = '';
    });
    tilesArea.appendChild(reset);
  }

  function renderQuestion(idx) {
    const q = questions[idx];
    currentIndex = idx;
    answered = false;
    feedbackArea.style.display = 'none';
    progressDisplay.textContent = idx + 1 + '/' + questions.length;

    let promptHtml = '<p class="quiz-kind">' + q.type.replace(/_/g, ' ') + '</p>';
    if (q.prompt) {
      promptHtml += '<p class="quiz-prompt font-kana">' + q.prompt + '</p>';
    }
    promptArea.innerHTML = promptHtml;

    if (q.type === 'build_word') {
      renderTiles(q);
    } else {
      renderMcq(q);
    }

    submitBtn.style.display = '';
    nextBtn.style.display = 'none';
    setTimeout(speakCurrent, 150);
  }

  function checkAnswer() {
    const q = questions[currentIndex];
    let userAnswer = '';
    if (q.type === 'build_word') {
      userAnswer = builtAnswer;
    } else {
      userAnswer = selected;
    }
    if (!userAnswer) return;

    const isCorrect = userAnswer === q.answer;
    outcomes.push({
      question_index: currentIndex,
      correct: isCorrect,
      kana_char: q.kana_char || (q.answer.length === 1 ? q.answer : q.prompt),
    });

    answered = true;
    submitBtn.style.display = 'none';
    nextBtn.style.display = '';

    if (isCorrect) {
      showFeedback('Benar! ' + (q.explain || ''), 'success');
      if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playCorrect();
    } else {
      showFeedback('Belum tepat. ' + (q.explain || ''), 'error');
      if (typeof window.KanaAudio !== 'undefined') window.KanaAudio.playWrong();
      if (heartsEnabled) setHearts(hearts - 1);
      reviewQueue.push(currentIndex); // re-ask at the end (main pass or review)
    }

    if (heartsEnabled && hearts <= 0) {
      submitBtn.style.display = 'none';
      nextBtn.style.display = 'none';
      setTimeout(finishLesson, 800);
    }
  }

  function finishLesson() {
    const correct = outcomes.filter((o) => o.correct).length;
    const total = questions.length;
    const payload = { outcomes: outcomes };

    fetch('/quiz/lesson/' + lessonId + '/result', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then((r) => r.json())
      .then((data) => {
        endAccuracy.textContent = correct + '/' + total;
        endXp.textContent = data.xp_earned;
        endScreen.style.display = 'flex';
        app.querySelector('#question-card').style.display = 'none';
        submitBtn.parentElement.style.display = 'none';
      })
      .catch(() => {
        endAccuracy.textContent = correct + '/' + total;
        endXp.textContent = '0';
        endScreen.style.display = 'flex';
      });
  }

  function advance() {
    if (inReview) {
      // Continue draining review items; cap attempts to avoid an endless loop.
      if (reviewQueue.length > 0 && reviewAttempts < questions.length * 3) {
        reviewAttempts++;
        const nextIdx = reviewQueue.shift();
        showFeedback('Ulangi soal yang salah tadi\u2026', 'info');
        renderQuestion(nextIdx);
      } else {
        inReview = false;
        finishLesson();
      }
      return;
    }
    // End of the main pass: switch to review mode for missed items.
    if (currentIndex + 1 >= questions.length) {
      if (reviewQueue.length > 0) {
        inReview = true;
        reviewAttempts++;
        const nextIdx = reviewQueue.shift();
        showFeedback('Ulangi soal yang salah tadi\u2026', 'info');
        renderQuestion(nextIdx);
        return;
      }
      finishLesson();
      return;
    }
    renderQuestion(currentIndex + 1);
  }

  submitBtn.addEventListener('click', checkAnswer);
  nextBtn.addEventListener('click', advance);
  listenBtn.addEventListener('click', speakCurrent);

  fetch('/quiz/lesson/' + lessonId + '/questions')
    .then((r) => r.json())
    .then((data) => {
      questions = data.questions || [];
      heartsEnabled = Boolean(data.hearts_enabled);
      if (!heartsEnabled) {
        heartsDisplay.style.display = 'none';
      } else {
        setHearts(5);
      }
      if (questions.length) {
        renderQuestion(0);
      } else {
        promptArea.innerHTML = '<p class="muted">Belum ada soal untuk pelajaran ini.</p>';
      }
    })
    .catch(() => {
      promptArea.innerHTML = '<p class="quiz-feedback quiz-feedback-error">Gagal memuat soal. Coba lagi.</p>';
    });
})();
