import {
  Menu
} from 'lucide-react';
import { useAppContext } from "../Context";

const Header = () => {
  const {
    sidebarOpen, setSidebarOpen
  } = useAppContext();

  return (
    <header className="h-16 flex items-center gap-3 px-4 shrink-0">
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="p-2 rounded-full hover:bg-[#e8eaed] dark:hover:bg-[#303134] text-[#5f6368] dark:text-[#9aa0a6] transition-all"
          aria-label="Open Sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>
      )}
      <h2 className="md:hidden text-md font-bold text-[#202124] dark:text-[#e3e3e3] truncate">
        AI Chatbot
      </h2>
    </header>
  )
}

export default Header;