import { useSyncExternalStore } from 'react';

export type PlaybackStatus = 'idle' | 'playing' | 'paused';

type PlaybackSnapshot = {
  status: PlaybackStatus;
  // Identifies the message being read, so each message's menu can show its own state
  id: string | null;
  // Index of the sentence being read, and how many sentences the message has
  sentence: number;
  sentenceCount: number;
};

const IDLE: PlaybackSnapshot = { status: 'idle', id: null, sentence: 0, sentenceCount: 0 };

let snapshot: PlaybackSnapshot = IDLE;
let activeUtterance: SpeechSynthesisUtterance | null = null;
// Speech synthesis cannot seek inside an utterance, so the message is read one sentence at a time
let sentences: string[] = [];
const listeners = new Set<() => void>();

const updateSnapshot = (next: PlaybackSnapshot) => {
  snapshot = next;
  listeners.forEach((listener) => listener());
};

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

const getSnapshot = () => snapshot;

// Clears the browser queue and drops any pending utterance before a new one starts or playback stops
const cancelActiveUtterance = () => {
  activeUtterance = null;
  window.speechSynthesis.cancel();
  // Some browsers stay paused after cancel(), which would leave the next message silent
  if (window.speechSynthesis.paused) {
    window.speechSynthesis.resume();
  }
};

const splitSentences = (text: string): string[] =>
  (text.match(/[^.!?]+[.!?]*/g) ?? []).map((sentence) => sentence.trim()).filter(Boolean);

const speakSentence = (id: string, index: number) => {
  cancelActiveUtterance();

  const utterance = new SpeechSynthesisUtterance(sentences[index]);
  // Only the current utterance may move playback on, so a cancelled one cannot touch a newer one
  utterance.onend = () => {
    if (activeUtterance !== utterance) {
      return;
    }

    if (index + 1 < sentences.length) {
      speakSentence(id, index + 1);
    } else {
      activeUtterance = null;
      updateSnapshot(IDLE);
    }
  };
  utterance.onerror = () => {
    if (activeUtterance === utterance) {
      activeUtterance = null;
      updateSnapshot(IDLE);
    }
  };

  activeUtterance = utterance;
  window.speechSynthesis.speak(utterance);
  updateSnapshot({ status: 'playing', id, sentence: index, sentenceCount: sentences.length });
};

export const speechPlayback = {
  play(id: string, text: string) {
    if (!('speechSynthesis' in window)) {
      return;
    }

    sentences = splitSentences(text);
    if (sentences.length === 0) {
      return;
    }

    speakSentence(id, 0);
  },

  pause() {
    if (snapshot.status !== 'playing') {
      return;
    }

    window.speechSynthesis.pause();
    updateSnapshot({ ...snapshot, status: 'paused' });
  },

  resume() {
    if (snapshot.status !== 'paused') {
      return;
    }

    window.speechSynthesis.resume();
    updateSnapshot({ ...snapshot, status: 'playing' });
  },

  // Moves to the sentence `offset` away. Going past the last sentence finishes playback
  seek(offset: number) {
    if (snapshot.status === 'idle' || snapshot.id === null) {
      return;
    }

    const index = snapshot.sentence + offset;
    if (index >= sentences.length) {
      speechPlayback.stop();
      return;
    }

    speakSentence(snapshot.id, Math.max(0, index));
  },

  // True while the given message is playing or paused
  isActive(id: string) {
    return snapshot.id === id && snapshot.status !== 'idle';
  },

  stop() {
    if (snapshot.status === 'idle') {
      return;
    }

    cancelActiveUtterance();
    sentences = [];
    updateSnapshot(IDLE);
  },
};

export const useSpeechPlayback = () => useSyncExternalStore(subscribe, getSnapshot);
