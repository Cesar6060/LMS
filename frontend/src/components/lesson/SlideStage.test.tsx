import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SlideStage } from './SlideStage';

function renderStage(overrides: Partial<Parameters<typeof SlideStage>[0]> = {}) {
  return render(
    <SlideStage
      slideKey="1-0"
      title="Overview"
      content={'# What Is a Robot?\n\nA vending machine is not one.'}
      direction="forward"
      {...overrides}
    />
  );
}

// Phase 62: the Present button moved out of the stage into the player content
// area — its tests live in PresentButton.test.tsx.
describe('SlideStage', () => {
  it('renders the title and markdown content', () => {
    renderStage();

    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(screen.getByText('A vending machine is not one.')).toBeInTheDocument();
  });

  it('renders no button of its own — the player owns the Present control', () => {
    renderStage();

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows the empty state when the page has no content or video', () => {
    renderStage({ content: '', title: '' });

    expect(screen.getByText('No content available for this page.')).toBeInTheDocument();
  });

  it('renders the image with its src and alt in image mode', () => {
    renderStage({ image: { url: 'https://cdn.example.com/slide-3.webp', alt: 'Slide 3: Sensors' } });

    const img = screen.getByRole('img', { name: 'Slide 3: Sensors' });
    expect(img).toHaveAttribute('src', 'https://cdn.example.com/slide-3.webp');
  });

  it('suppresses the title heading in image mode', () => {
    renderStage({ image: { url: 'https://cdn.example.com/slide-3.webp', alt: 'Slide 3' } });

    expect(screen.queryByRole('heading', { name: 'Overview' })).not.toBeInTheDocument();
  });

  it('does not render markdown content or the empty state in image mode', () => {
    renderStage({ image: { url: 'https://cdn.example.com/slide-3.webp', alt: 'Slide 3' } });

    expect(screen.queryByRole('heading', { name: 'What Is a Robot?' })).not.toBeInTheDocument();
    expect(screen.queryByText('A vending machine is not one.')).not.toBeInTheDocument();
    expect(screen.queryByText('No content available for this page.')).not.toBeInTheDocument();
  });

  it('does not render the empty state in image mode even with no content', () => {
    renderStage({
      content: '',
      title: '',
      image: { url: 'https://cdn.example.com/slide-3.webp', alt: 'Slide 3' },
    });

    expect(screen.queryByText('No content available for this page.')).not.toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Slide 3' })).toBeInTheDocument();
  });

  it('keeps title and content rendering unchanged when no image is set', () => {
    renderStage();

    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByText('A vending machine is not one.')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
