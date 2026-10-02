import { readStore, writeStore } from "./storage";

// A camera shutter synthesized with Web Audio: no audio files, nothing autoplays.
// Sound is OFF by default and only plays after a user gesture.
const KEY = "nvl.sound";
let ctx: AudioContext | null = null;

export const soundEnabled = () => readStore<boolean>(KEY, false);
export const setSoundEnabled = (on: boolean) => writeStore(KEY, on);

export function playShutter(): void {
  if (!soundEnabled()) return;
  try {
    const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    ctx ??= new AC();
    const now = ctx.currentTime;
    const click = (at: number, freq: number, gain: number) => {
      const len = 0.045;
      const buffer = ctx!.createBuffer(1, Math.floor(ctx!.sampleRate * len), ctx!.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 3);
      const src = ctx!.createBufferSource();
      src.buffer = buffer;
      const filter = ctx!.createBiquadFilter();
      filter.type = "bandpass";
      filter.frequency.value = freq;
      const g = ctx!.createGain();
      g.gain.value = gain;
      src.connect(filter).connect(g).connect(ctx!.destination);
      src.start(now + at);
    };
    click(0, 2400, 0.5);
    click(0.07, 1500, 0.35);
  } catch {
    /* audio unavailable */
  }
}
