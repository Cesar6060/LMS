// Vitest setup (phase 55, D1). Registers jest-dom's matchers so component
// tests can use toBeInTheDocument() and friends, and clears the DOM between
// tests so one test's render can't leak into the next.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
  cleanup();
});
