import ChatContainer from './components/ChatContainer';
import Sidebar from './components/Sidebar';
import PromptInput from './components/PromptInput';
import Header from './components/Header';

export default function App() {
  return (
    <div className="font-sans flex h-screen w-screen overflow-hidden bg-white dark:bg-[#131314] text-[#202124] dark:text-[#e3e3e3]">
      <Sidebar/>
      <main className="flex-1 flex flex-col h-full relative overflow-hidden w-full">
        <Header/>
        <div className="flex-1 overflow-y-auto p-4 w-full">
          <div className="max-w-3xl mx-auto w-full space-y-6">
            <ChatContainer/>
          </div>
        </div>
        <div className="p-4 bg-white dark:bg-[#131314]">
          <div className="max-w-3xl mx-auto w-full">
            <PromptInput/>
          </div>
        </div>
      </main>
    </div>
  );
}