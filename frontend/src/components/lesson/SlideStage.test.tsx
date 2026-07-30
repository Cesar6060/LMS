import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SlideStage } from './SlideStage';

function renderStage(overrides: Partial<Parameters<typeof SlideStage>[0]> = {}) {
  return render(
    <SlideStage
      slideKey="1-0"
      title="Overview"
      content={'# What Is a Robot?\n\nA vending machine is not one.'}
      direction="forward"
      isPresenting={false}
      onTogglePresent={vi.fn()}
      {...overrides}
    />
  );
}

describe('SlideStage', () => {
  beforeEach(() => {
    // jsdom has no Fullscreen API; the stage gates its Present button on it.
    Object.defineProperty(document, 'fullscreenEnabled', {
      value: true,
      configurable: true,
    });
  });

  it('renders the title and markdown content', () => {
    renderStage();

    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(screen.getByText('A vending machine is not one.')).toBeInTheDocument();
  });

  it('shows Present when not presenting and fires onTogglePresent on click', () => {
    const onTogglePresent = vi.fn();
    renderStage({ onTogglePresent });

    const button = screen.getByRole('button', { name: 'Present fullscreen (F)' });
    fireEvent.click(button);

    expect(onTogglePresent).toHaveBeenCalledTimes(1);
  });

  it('shows Exit while presenting', () => {
    renderStage({ isPresenting: true });

    expect(screen.getByRole('button', { name: 'Exit fullscreen (Esc)' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Present fullscreen (F)' })).not.toBeInTheDocument();
  });

  it('hides the Present button where the Fullscreen API is unavailable', () => {
    Object.defineProperty(document, 'fullscreenEnabled', {
      value: false,
      configurable: true,
    });

    renderStage();

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows the empty state when the page has no content or video', () => {
    renderStage({ content: '', title: '' });

    expect(screen.getByText('No content available for this page.')).toBeInTheDocument();
  });
});
