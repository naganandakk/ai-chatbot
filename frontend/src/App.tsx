import { useEffect, useState } from 'react';
import ChatContainer from './components/ChatContainer';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ErrorStack from './components/ErrorStack';
import PlaybackControl from './components/PlaybackControl';

const App = () => {
  // iOS Safari pans the page when the keyboard opens, so pin the app to the visible area
  const [visibleArea, setVisibleArea] = useState<{ top: number; height: number } | null>(null);

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) {
      return;
    }
    const updateVisibleArea = () => {
      setVisibleArea({ top: viewport.offsetTop, height: viewport.height });
    };

    updateVisibleArea();
    viewport.addEventListener('resize', updateVisibleArea);
    viewport.addEventListener('scroll', updateVisibleArea);

    return () => {
      viewport.removeEventListener('resize', updateVisibleArea);
      viewport.removeEventListener('scroll', updateVisibleArea);
    };
  }, []);

  return (
    <div
      style={visibleArea ? { top: visibleArea.top, height: visibleArea.height } : undefined}
      className={`font-sans fixed left-0 flex w-screen overflow-hidden bg-white dark:bg-[#131314] text-[#202124] dark:text-[#e3e3e3] ${visibleArea ? '' : 'h-dvh'}`}>
      <ErrorStack/>
      <Sidebar/>
      <main className="flex-1 flex flex-col h-full relative overflow-hidden w-full">
        <PlaybackControl/>
        <Header/>
        <ChatContainer/>
      </main>
    </div>
  );
};

export default App;