import { useEffect } from 'react';
import { Pause, Play, SkipBack, SkipForward, X, type LucideIcon } from 'lucide-react';
import { useAppContext } from '../Context';
import { speechPlayback, useSpeechPlayback } from '../speech';

type ControlButtonProps = {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
};

const ControlButton = ({ label, icon: Icon, onClick }: ControlButtonProps) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={label}
    title={label}
    className="p-2 rounded-full text-[#3c4043] dark:text-[#e3e3e3] hover:bg-[#e8eaed] dark:hover:bg-[#303134] transition-colors"
  >
    <Icon className="w-5 h-5" />
  </button>
);

type PlaybackControlProps = {
  // Floating sits over the chat's top-right corner on desktop. Otherwise it sticks to the top of the messages
  floating?: boolean;
};

const PlaybackControl = ({ floating = false }: PlaybackControlProps) => {
  const { activeSession } = useAppContext();
  const { status, sentence, sentenceCount } = useSpeechPlayback();

  // Playback belongs to the chat it started in, so changing sessions stops it
  useEffect(() => {
    speechPlayback.stop();
  }, [activeSession?.id]);

  if (status === 'idle') {
    return null;
  }

  const isPlaying = status === 'playing';

  return (
    <div
      role="region"
      aria-label="Audio playback"
      className={`${floating ? '' : 'sticky top-0 z-10 '}flex items-center justify-between gap-2 px-4 py-1.5 rounded-xl border border-[#1a73e8]/40 bg-white dark:bg-[#1e1f20] shadow-[0_8px_24px_rgba(32,33,36,0.28)] ring-1 ring-[#1a73e8]/20`}
    >
      <span className="text-sm text-[#5f6368] dark:text-[#9aa0a6] truncate">
        Reading {sentence + 1} of {sentenceCount}
      </span>
      <div className="flex items-center gap-1">
        <ControlButton label="Rewind" icon={SkipBack} onClick={() => speechPlayback.seek(-1)} />
        <ControlButton
          label={isPlaying ? 'Pause audio' : 'Resume audio'}
          icon={isPlaying ? Pause : Play}
          onClick={isPlaying ? speechPlayback.pause : speechPlayback.resume}
        />
        <ControlButton label="Forward" icon={SkipForward} onClick={() => speechPlayback.seek(1)} />
        <ControlButton label="Close player" icon={X} onClick={speechPlayback.stop} />
      </div>
    </div>
  );
};

export default PlaybackControl;
