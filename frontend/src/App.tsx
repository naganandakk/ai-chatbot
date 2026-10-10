import ChatContainer from './components/ChatContainer';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ErrorStack from './components/ErrorStack';
import PlaybackControl from './components/PlaybackControl';

const App = () => {
  return (
    <div className="font-sans flex h-screen w-screen overflow-hidden bg-white dark:bg-[#131314] text-[#202124] dark:text-[#e3e3e3]">
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