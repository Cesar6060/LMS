import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme, persist?: boolean) => void;
  resolvedTheme: 'light' | 'dark';
  resetTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    // Check localStorage first (for guest/pre-login preference)
    const stored = localStorage.getItem('theme') as Theme | null;
    if (stored && ['light', 'dark', 'system'].includes(stored)) {
      return stored;
    }
    return 'system';
  });

  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');

  // Update the actual theme based on setting and system preference
  useEffect(() => {
    const updateTheme = () => {
      let effectiveTheme: 'light' | 'dark';

      if (theme === 'system') {
        effectiveTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light';
      } else {
        effectiveTheme = theme;
      }

      setResolvedTheme(effectiveTheme);

      // Apply to document
      if (effectiveTheme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    };

    updateTheme();

    // Listen for system theme changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (theme === 'system') {
        updateTheme();
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme]);

  // Set theme - optionally persist to localStorage (for guest users on login page)
  const setTheme = (newTheme: Theme, persist: boolean = true) => {
    setThemeState(newTheme);
    if (persist) {
      localStorage.setItem('theme', newTheme);
    }
  };

  // Reset theme on logout - clears localStorage and goes back to system default
  const resetTheme = () => {
    localStorage.removeItem('theme');
    setThemeState('system');
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme, resetTheme }}>
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
