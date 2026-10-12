import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import App from './App.tsx'
import { ContextProvider } from "./Context";
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ContextProvider>
        {/* Both routes render the same app, so the session in the URL is the only thing that changes */}
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/sessions/:sessionId" element={<App />} />
        </Routes>
      </ContextProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
