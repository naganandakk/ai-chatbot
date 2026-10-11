import { Mic, Square } from 'lucide-react';

interface VoiceInputBtnProps {
  isListening: boolean;
  disabled: boolean;
  onToggle: () => void;
}

const VoiceInputBtn = ({ isListening, disabled, onToggle }: VoiceInputBtnProps) => {
  if (isListening) {
    // While listening, the button is a filled red pill with a visible label, so stopping is the obvious action
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label="Stop listening"
        aria-pressed={true}
        title="Stop listening"
        className="shrink-0 flex items-center gap-2 my-1.5 px-3 py-2 rounded-full bg-[#d93025] text-white text-sm font-medium hover:bg-[#b3261e] transition-colors"
      >
        <span className="relative flex w-2.5 h-2.5" aria-hidden="true">
          <span className="absolute inline-flex w-full h-full rounded-full bg-white opacity-75 animate-ping" />
          <span className="relative inline-flex w-2.5 h-2.5 rounded-full bg-white" />
        </span>
        <span>Listening</span>
        <Square className="w-3 h-3 fill-current" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      aria-label="Start voice prompt"
      aria-pressed={false}
      title="Start voice prompt"
      className="shrink-0 p-2 rounded-full text-[#5f6368] dark:text-[#9aa0a6] hover:bg-[#e8eaed] dark:hover:bg-[#303134] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
    >
      <Mic className="w-4 h-4" />
    </button>
  );
};

export default VoiceInputBtn;
