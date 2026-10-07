/**
 * Kana Chat audio helper - vanilla JS port of the React app's utils/audio.ts.
 * Web Speech API (ja-JP) for pronunciation + WebAudio for UI sound effects.
 * Exposes a single global: window.KanaAudio
 *
 * Usage in a template:
 *   <script src="{{ url_for('static', filename='js/tts.js') }}"></script>
 *   KanaAudio.speak('こんにちは');  KanaAudio.playCorrect();  KanaAudio.playWrong();
 */
(function () {
  let audioCtx = null;

  function getAudioContext() {
    if (typeof window === 'undefined') return null;
    if (!audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) audioCtx = new Ctx();
    }
    if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
    return audioCtx;
  }

  function findJaVoice() {
    if (!('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    return (
      voices.find((v) => {
        const l = (v.lang || '').toLowerCase();
        return l.includes('ja') || l.includes('jp');
      }) || null
    );
  }

  function checkVoices() {
    return Boolean(findJaVoice());
  }

  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    checkVoices();
    window.speechSynthesis.onvoiceschanged = checkVoices;
  }

  function playMelodicChime(seedText) {
    const ctx = getAudioContext();
    if (!ctx) return;
    const now = ctx.currentTime;
    const code = (seedText && seedText.charCodeAt(0)) || 12354;
    const baseFreq = 380 + (code % 20) * 15;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(baseFreq, now);
    osc.frequency.exponentialRampToValueAtTime(baseFreq * 1.33, now + 0.15);
    gain.gain.setValueAtTime(0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.35);
  }

  // Speak Japanese text. Returns { playedSpeech: boolean, message?: string }.
  function speak(text, rate = 0.85, onEnd) {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return { playedSpeech: false };
    }
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'ja-JP';
      u.rate = rate;
      const ja = findJaVoice();
      if (ja) {
        u.voice = ja;
        if (onEnd) u.onend = onEnd;
        window.speechSynthesis.speak(u);
        return { playedSpeech: true };
      }
      playMelodicChime(text);
      if (onEnd) setTimeout(onEnd, 400);
      return {
        playedSpeech: false,
        message: 'Suara Jepang (ja-JP) belum terpasang di perangkat ini. Nada panduan melodi dibunyikan.',
      };
    } catch (err) {
      console.warn('Speech synthesis error:', err);
    }
    playMelodicChime(text);
    if (onEnd) setTimeout(onEnd, 300);
    return { playedSpeech: false, message: 'Synthesizer suara melodi alternatif digunakan.' };
  }

  // Japanese "pin-pon" correct chime.
  function playCorrectChime() {
    const ctx = getAudioContext();
    if (!ctx) return;
    const now = ctx.currentTime;
    const osc1 = ctx.createOscillator();
    const g1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(1046.5, now);
    g1.gain.setValueAtTime(0.25, now);
    g1.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
    osc1.connect(g1);
    g1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.4);

    const osc2 = ctx.createOscillator();
    const g2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(1318.51, now + 0.16);
    g2.gain.setValueAtTime(0.3, now + 0.16);
    g2.gain.exponentialRampToValueAtTime(0.001, now + 0.7);
    osc2.connect(g2);
    g2.connect(ctx.destination);
    osc2.start(now + 0.16);
    osc2.stop(now + 0.7);
  }

  // Dissonant "bu-bu" wrong buzzer.
  function playWrongBuzzer() {
    const ctx = getAudioContext();
    if (!ctx) return;
    const now = ctx.currentTime;
    const pulse = (start) => {
      const o1 = ctx.createOscillator();
      const o2 = ctx.createOscillator();
      const g = ctx.createGain();
      o1.type = 'sawtooth';
      o2.type = 'square';
      o1.frequency.setValueAtTime(130.81, start);
      o2.frequency.setValueAtTime(138.59, start);
      g.gain.setValueAtTime(0.22, start);
      g.gain.linearRampToValueAtTime(0.001, start + 0.16);
      o1.connect(g);
      o2.connect(g);
      g.connect(ctx.destination);
      o1.start(start);
      o2.start(start);
      o1.stop(start + 0.16);
      o2.stop(start + 0.16);
    };
    pulse(now);
    pulse(now + 0.18);
  }

  function playKeyClick() {
    const ctx = getAudioContext();
    if (!ctx) return;
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(600, now);
    osc.frequency.exponentialRampToValueAtTime(800, now + 0.04);
    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.04);
  }

  function voiceStatus() {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return { supported: false, hasJaVoice: false, message: 'Browser Anda tidak mendukung Web Speech API.' };
    }
    return checkVoices()
      ? { supported: true, hasJaVoice: true, message: 'Suara penutur asli Bahasa Jepang siap digunakan!' }
      : { supported: true, hasJaVoice: false, message: 'Paket suara Bahasa Jepang (ja-JP) belum terpasang. Synthesizer nada melodi tetap aktif.' };
  }

  window.KanaAudio = {
    speak,
    playCorrect: playCorrectChime,
    playWrong: playWrongBuzzer,
    playKeyClick,
    playSuccess: playCorrectChime,
    playError: playWrongBuzzer,
    voiceStatus,
  };
})();
