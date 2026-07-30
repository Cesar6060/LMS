import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SectionEditor } from './SectionEditor';

const mockGetLessonSections = vi.hoisted(() => vi.fn());

vi.mock('@/services/courses', () => ({
  courseService: { getLessonSections: mockGetLessonSections },
}));
vi.mock('@/contexts/useToast', () => ({
  useToast: () => ({ show: vi.fn() }),
}));

const PASTED = [
  '## Alpha', '', 'AAA unique alpha body', '', '---', '',
  '## Beta', '', 'BBB unique beta body', '', '---', '',
  '## Gamma', '', 'CCC unique gamma body',
].join('\n');

/**
 * Text of the rendered preview panes only — the pasted source also lives in a
 * textarea, so a document-wide text query matches each body twice.
 */
const previewTexts = () =>
  Array.from(document.querySelectorAll('.lesson-markdown')).map(el => el.textContent ?? '');

async function openPreviewWithThreeCards() {
  render(<SectionEditor lessonId={1} lessonTitle="Naming Conventions" />);

  fireEvent.click(await screen.findByRole('button', { name: /paste to add pages/i }));
  fireEvent.change(screen.getByLabelText(/pasted markdown/i), { target: { value: PASTED } });
  fireEvent.click(screen.getByRole('button', { name: /preview split/i }));

  expect(await screen.findByText('3 pages to add')).toBeInTheDocument();
  // The previews are debounced — wait for the first render to settle.
  await waitFor(() => expect(previewTexts()).toHaveLength(3));
  expect(previewTexts()[0]).toContain('AAA unique alpha body');
}

describe('SectionEditor — paste-to-split previews (phase 62)', () => {
  beforeEach(() => {
    mockGetLessonSections.mockReset().mockResolvedValue([]);
  });

  it('never shows a removed page under the row that shifted up', async () => {
    await openPreviewWithThreeCards();

    const removeButtons = screen.getAllByRole('button', { name: /remove this page/i });
    expect(removeButtons).toHaveLength(3);

    // Drop page 1. Row 0 now holds Beta. Because the rows carry a stable
    // per-card key rather than being keyed by array index, React unmounts
    // Alpha's row instead of handing Beta's content to Alpha's still-debouncing
    // preview — keyed by index, row 0 kept rendering Alpha for ~200ms.
    fireEvent.click(removeButtons[0]);

    expect(screen.getByText('2 pages to add')).toBeInTheDocument();
    expect(previewTexts().join('|')).not.toContain('AAA unique alpha body');
  });

  it('keeps each row’s preview matched to its own page after a removal', async () => {
    await openPreviewWithThreeCards();

    fireEvent.click(screen.getAllByRole('button', { name: /remove this page/i })[0]);

    const previews = previewTexts();
    expect(previews).toHaveLength(2);
    expect(previews[0]).toContain('BBB unique beta body');
    expect(previews[1]).toContain('CCC unique gamma body');
  });
});
