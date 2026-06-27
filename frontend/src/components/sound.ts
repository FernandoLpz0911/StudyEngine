// Arcade-style Web Audio feedback (no deps). 8-bit square-wave coins/power-ups
// that escalate with the streak. Gated by the same localStorage flag the sound
// toggle writes. Silent if the browser blocks audio.

const SOUND_KEY = "studyengine.sound";
let ac: AudioContext | null = null;

function ctx(): AudioContext | null {
  if (localStorage.getItem(SOUND_KEY) !== "1") return null;
  try {
    ac = ac ?? new AudioContext();
    return ac;
  } catch {
    return null;
  }
}

/** Schedule one note with a short percussive envelope. */
function tone(
  a: AudioContext,
  freq: number,
  start: number,
  dur: number,
  type: OscillatorType = "square",
  peak = 0.08,
) {
  const o = a.createOscillator();
  const g = a.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, start);
  o.connect(g);
  g.connect(a.destination);
  g.gain.setValueAtTime(0.0001, start);
  g.gain.exponentialRampToValueAtTime(peak, start + 0.008);
  g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
  o.start(start);
  o.stop(start + dur + 0.02);
}

// Pentatonic-ish coin steps; the run gets longer and higher with the streak.
const COIN = [523.25, 659.25, 783.99, 1046.5, 1318.5];

/** Correct: ascending coin arpeggio; brighter/longer as the streak climbs. */
export function playCorrect(streak: number) {
  const a = ctx();
  if (!a) return;
  const t = a.currentTime;
  const n = Math.min(2 + Math.floor(streak / 3), COIN.length); // 2..5 notes
  const shift = Math.min(streak, 8) * 18; // pitch climbs with combo
  const step = 0.06;
  for (let i = 0; i < n; i++) {
    tone(a, COIN[i] + shift, t + i * step, 0.12, "square", 0.07);
  }
  // Sparkle on the last note for a bigger combo.
  if (streak >= 5) tone(a, COIN[n - 1] * 2 + shift, t + n * step, 0.1, "triangle", 0.05);
}

/** Wrong: short descending low buzz — clearly negative but not harsh. */
export function playWrong() {
  const a = ctx();
  if (!a) return;
  const t = a.currentTime;
  tone(a, 196, t, 0.12, "square", 0.06);
  tone(a, 146.83, t + 0.1, 0.16, "square", 0.06);
}

/** Level-up: rising power-up run, fuller and longer. */
export function playLevelUp() {
  const a = ctx();
  if (!a) return;
  const t = a.currentTime;
  const run = [523.25, 659.25, 783.99, 1046.5, 1318.5, 1568.0];
  run.forEach((f, i) => {
    tone(a, f, t + i * 0.07, 0.16, "square", 0.07);
    tone(a, f * 1.5, t + i * 0.07, 0.16, "triangle", 0.03); // harmony
  });
}
