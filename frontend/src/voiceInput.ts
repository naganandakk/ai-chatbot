import { useCallback, useEffect, useRef, useState } from 'react';

// The DOM typings in TypeScript do not include the Web Speech recognition API, so the parts used here are declared
interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: { readonly transcript: string };
}

interface SpeechRecognitionEventLike {
  readonly resultIndex: number;
  readonly results: { readonly length: number; [index: number]: SpeechRecognitionResultLike };
}

interface SpeechRecognitionErrorEventLike {
  readonly error: string;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type SpeechRecognitionWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

const getRecognitionConstructor = (): SpeechRecognitionConstructor | null => {
  const speechWindow = window as SpeechRecognitionWindow;
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
};

// Permission and network errors are worth telling the user about. Silence and manual stops are not
const REPORTED_ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone access was denied. Allow it in your browser settings to use voice prompts.',
  'service-not-allowed': 'Voice prompts are not available in this browser.',
  'audio-capture': 'No microphone was found.',
  network: 'Voice prompts need a network connection.',
};

type UseVoiceInputOptions = {
  // Receives the prompt text as it should read: the text typed before listening, plus the speech so far
  onChange: (text: string) => void;
  currentText: string;
  onError: (message: string) => void;
};

export const useVoiceInput = ({ onChange, currentText, onError }: UseVoiceInputOptions) => {
  const [isListening, setIsListening] = useState<boolean>(false);
  const supported = getRecognitionConstructor() !== null;
  // Explains why voice is unavailable, so the button can say so instead of silently hiding
  const unsupportedReason = supported
    ? null
    : window.isSecureContext
      ? "Voice prompts are not supported in this browser. Try Chrome on Android or Safari on iPhone."
      : "Voice prompts need a secure (HTTPS) connection.";
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  // The prompt text when listening started. Speech is appended to it, so interim results replace the last guess
  const baseTextRef = useRef<string>('');
  // The latest callbacks, so the recognizer always reports to current state
  const onChangeRef = useRef(onChange);
  const onErrorRef = useRef(onError);
  const currentTextRef = useRef(currentText);

  useEffect(() => {
    onChangeRef.current = onChange;
    onErrorRef.current = onError;
    currentTextRef.current = currentText;
  });

  // Ends listening and keeps the words recognized so far
  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  // Ends listening and drops anything not yet delivered, so a late result cannot refill a cleared prompt
  const cancel = useCallback(() => {
    recognitionRef.current?.abort();
  }, []);

  const start = useCallback(() => {
    const Constructor = getRecognitionConstructor();
    if (!Constructor || recognitionRef.current) {
      return;
    }

    const recognition = new Constructor();
    recognition.lang = navigator.language;
    recognition.continuous = true;
    recognition.interimResults = true;

    baseTextRef.current = currentTextRef.current;
    let finalText = '';

    recognition.onresult = (event) => {
      let interimText = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;

        if (result.isFinal) {
          finalText += transcript;
        } else {
          interimText += transcript;
        }
      }

      const spoken = (finalText + interimText).trim();
      const base = baseTextRef.current;
      const separator = base && spoken && !/\s$/.test(base) ? ' ' : '';
      onChangeRef.current(`${base}${separator}${spoken}`);
    };

    recognition.onerror = (event) => {
      const message = REPORTED_ERRORS[event.error];
      if (message) {
        onErrorRef.current(message);
      }
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, []);

  // Stops the recognizer without reporting results from a page that is going away
  useEffect(() => {
    return () => {
      const recognition = recognitionRef.current;
      if (recognition) {
        recognition.onresult = null;
        recognition.onerror = null;
        recognition.onend = null;
        recognition.abort();
        recognitionRef.current = null;
      }
    };
  }, []);

  return { supported, unsupportedReason, isListening, start, stop, cancel };
};
