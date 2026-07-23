import { createContext, useContext } from 'react';

export interface ThemeContextType {
  theme: 'dark';
  setTheme: (theme: 'dark') => void;
  resolvedTheme: 'dark';
  resetTheme: () => void;
}

// Context + hook live apart from ThemeProvider so ThemeContext.tsx only
// exports a component (react-refresh/only-export-components).
export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
