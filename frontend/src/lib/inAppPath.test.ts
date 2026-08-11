import { describe, expect, it } from 'vitest';
import { isInAppPath } from './inAppPath';

describe('isInAppPath', () => {
  it('accepts the paths notifications actually carry', () => {
    expect(isInAppPath('/courses/ROB101')).toBe(true);
    expect(isInAppPath('/courses/ROB101/lessons/12')).toBe(true);
    expect(isInAppPath('/dashboard?tab=badges')).toBe(true);
    expect(isInAppPath('/')).toBe(true);
  });

  it('rejects anything that could leave the app', () => {
    expect(isInAppPath('//example.com/phish')).toBe(false);
    expect(isInAppPath('https://example.com/phish')).toBe(false);
    expect(isInAppPath('http://example.com')).toBe(false);
    expect(isInAppPath('javascript:alert(1)')).toBe(false);
    expect(isInAppPath('/\\example.com')).toBe(false);
  });

  it('rejects a path that is not anchored at the root', () => {
    expect(isInAppPath('dashboard')).toBe(false);
    expect(isInAppPath('')).toBe(false);
  });

  it('sees through the whitespace and control characters a browser would strip', () => {
    // "/\t/example.com" parses as protocol-relative once the tab is removed.
    expect(isInAppPath('/\t/example.com')).toBe(false);
    expect(isInAppPath('/\n/example.com')).toBe(false);
    expect(isInAppPath('  //example.com')).toBe(false);
    expect(isInAppPath(' javascript:alert(1)')).toBe(false);
  });
});
