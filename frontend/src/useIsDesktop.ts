import { useEffect, useState } from "react";

const DESKTOP_QUERY = "(min-width: 768px)";

// Tracks the md breakpoint, so layout pieces can be rendered in one place per screen size
export const useIsDesktop = (): boolean => {
  const [isDesktop, setIsDesktop] = useState<boolean>(() => window.matchMedia(DESKTOP_QUERY).matches);

  useEffect(() => {
    const media = window.matchMedia(DESKTOP_QUERY);
    const update = () => setIsDesktop(media.matches);

    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return isDesktop;
};
