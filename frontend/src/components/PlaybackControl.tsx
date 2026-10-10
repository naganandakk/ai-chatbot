import { useEffect } from 'react';
import { Pause, Play } from 'lucide-react';
import { useAppContext } from '../Context';
import { speechPlayback, useSpeechPlayback } from '../speech';

// Floating control that stays visible while a message is being read aloud
const PlaybackControl = () => {
  const { activeSession } = useAppContext();
  const { status } = useSpeechPlayback();

  // Playback belongs to the chat it started in, so changing sessions stops it
  useEffect(() => {
    speechPlayback.stop();
  }, [activeSession?.id]);

  if (status === 'idle') {
    return null;
  }

  const isPlaying = status === 'playing';
  const Icon = isPlaying ? Pause : Play;

  return (
    <button
      type="button"
      onClick={isPlaying ? speechPlayback.pause : speechPlayback.resume}
      aria-label={isPlaying ? 'Pause audio' : 'Resume audio'}
      title={isPlaying ? 'Pause audio' : 'Resume audio'}
      className="absolute top-4 right-4 z-40 p-2.5 rounded-full bg-white text-[#3c4043] shadow-md border border-[#dadce0] hover:bg-[#f1f3f4] transition-colors"
    >
      <Icon className="w-5 h-5" />
    </button>
  );
};

export default PlaybackControl;
