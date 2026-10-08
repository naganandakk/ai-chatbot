import React, { useContext } from 'react';
import { Context } from "../Context";

export const ErrorStack = () => {
  const { errors, removeError } = useContext(Context);

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-3 w-full max-w-sm pointer-events-none">
      {errors.map((error) => (
        <div
          key={error.id}
          className="w-full pointer-events-auto animate-fade-in-down"
        >
          {/* Google Material-styled Toast Notification card */}
          <div className="bg-[#202124] text-white px-4 py-3 rounded-md shadow-xl flex items-start justify-between space-x-3 border border-[#303134]">
            <div className="flex items-start space-x-3 min-w-0 pt-0.5">
              {/* Warning Icon */}
              <svg className="w-5 h-5 text-[#EE675C] shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span className="text-sm font-sans text-gray-200 leading-tight block break-words">
                {error.message}
              </span>
            </div>

            <button
              onClick={() => removeError(error.id)}
              className="text-[#8AB4F8] hover:text-[#ADCCFF] text-xs font-semibold tracking-wide uppercase px-2 py-1 rounded transition-colors shrink-0 focus:outline-none"
            >
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};
