import { createContext, useContext, useEffect, ReactNode } from 'react';

interface ThemeContextType {
  theme: 'dark';
  setTheme: (theme: 'dark') => void;
  resolvedTheme: 'dark';
  resetTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

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

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
