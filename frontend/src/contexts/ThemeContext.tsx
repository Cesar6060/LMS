import { useEffect, ReactNode } from 'react';
import { ThemeContext } from './useTheme';

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Force dark mode for gaming theme
  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  // No-op functions since we're forcing dark mode
  const setTheme = () => {};
  const resetTheme = () => {};

  return (
    <ThemeContext.Provider value={{ theme: 'dark', setTheme, resolvedTheme: 'dark', resetTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
