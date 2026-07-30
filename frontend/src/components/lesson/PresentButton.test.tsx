import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PresentButton } from './PresentButton';

describe('PresentButton', () => {
  beforeEach(() => {
    // jsdom has no Fullscreen API; the button gates itself on it.
    Object.defineProperty(document, 'fullscreenEnabled', {
      value: true,
      configurable: true,
    });
  });

  it('shows Present when not presenting and fires onToggle on click', () => {
    const onToggle = vi.fn();
    render(<PresentButton isPresenting={false} onToggle={onToggle} />);

    const button = screen.getByRole('button', { name: 'Present fullscreen (F)' });
    fireEvent.click(button);

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('shows Exit while presenting', () => {
    render(<PresentButton isPresenting onToggle={vi.fn()} />);

    expect(screen.getByRole('button', { name: 'Exit fullscreen (Esc)' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Present fullscreen (F)' })).not.toBeInTheDocument();
  });

  it('renders nothing where the Fullscreen API is unavailable', () => {
    Object.defineProperty(document, 'fullscreenEnabled', {
      value: false,
      configurable: true,
    });

    render(<PresentButton isPresenting={false} onToggle={vi.fn()} />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
