import { useSyncExternalStore } from 'react';

export type PlaybackStatus = 'idle' | 'playing' | 'paused';

type PlaybackSnapshot = {
  status: PlaybackStatus;
  // Identifies the message being read, so each message's menu can show its own state
  id: string | null;
};

let snapshot: PlaybackSnapshot = { status: 'idle', id: null };
let activeUtterance: SpeechSynthesisUtterance | null = null;
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

export const speechPlayback = {
  play(id: string, text: string) {
    if (!('speechSynthesis' in window)) {
      return;
    }

    cancelActiveUtterance();

    const utterance = new SpeechSynthesisUtterance(text);
    // Only the current utterance may reset the state, so a cancelled one cannot clear a newer one
    const finish = () => {
      if (activeUtterance === utterance) {
        activeUtterance = null;
        updateSnapshot({ status: 'idle', id: null });
      }
    };
    utterance.onend = finish;
    utterance.onerror = finish;

    activeUtterance = utterance;
    window.speechSynthesis.speak(utterance);
    updateSnapshot({ status: 'playing', id });
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

  // True while the given message is playing or paused
  isActive(id: string) {
    return snapshot.id === id && snapshot.status !== 'idle';
  },

  stop() {
    if (snapshot.status === 'idle') {
      return;
    }

    cancelActiveUtterance();
    updateSnapshot({ status: 'idle', id: null });
  },
};

export const useSpeechPlayback = () => useSyncExternalStore(subscribe, getSnapshot);
