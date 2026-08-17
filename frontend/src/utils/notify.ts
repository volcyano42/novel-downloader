let audioCtx: AudioContext | null = null;

function beep() {
  try {
    audioCtx = audioCtx ?? new AudioContext();
    if (audioCtx.state === "suspended") void audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.25, audioCtx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.6);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.6);
  } catch {
    /* AudioContext 未激活（无用户交互）时静默 */
  }
}

export function notifyUser(sound: "bell" | "system" | "none", title: string) {
  if (sound === "bell") {
    beep();
  } else if (sound === "system") {
    if ("Notification" in window) {
      if (Notification.permission === "granted") {
        new Notification(title);
      } else if (Notification.permission !== "denied") {
        void Notification.requestPermission();
      }
    }
  }
}
