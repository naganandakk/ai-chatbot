import { useAppContext } from "../Context";

type NotificationVariant = "error" | "success";

const variantStyles: Record<NotificationVariant, { iconClass: string; path: string }> = {
  error: {
    iconClass: "text-[#EE675C]",
    path: "M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z",
  },
  success: {
    iconClass: "text-[#81C995]",
    path: "M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z",
  },
};

const NotificationStack = () => {
  const { notifications, dismissNotification } = useAppContext();

  return (
    <div
      aria-live="polite"
      className="fixed top-4 right-4 z-50 flex flex-col gap-3 w-full max-w-sm pointer-events-none"
    >
      {notifications.map((notification) => {
        const { iconClass, path } = variantStyles[notification.variant];

        return (
          <div
            key={notification.id}
            className="w-full pointer-events-auto animate-fade-in-down"
          >
            {/* Google Material-styled Toast Notification card */}
            <div className="bg-[#202124] text-white px-4 py-3 rounded-md shadow-xl flex items-start justify-between space-x-3 border border-[#303134]">
              <div className="flex items-start space-x-3 min-w-0 pt-0.5">
                <svg className={`w-5 h-5 shrink-0 mt-0.5 ${iconClass}`} fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d={path} clipRule="evenodd" />
                </svg>
                <span className="text-sm font-sans text-gray-200 leading-tight block break-words">
                  {notification.message}
                </span>
              </div>

              <button
                onClick={() => dismissNotification(notification.id)}
                className="text-[#8AB4F8] hover:text-[#ADCCFF] text-xs font-semibold tracking-wide uppercase px-2 py-1 rounded transition-colors shrink-0 focus:outline-none"
              >
                Dismiss
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default NotificationStack;
