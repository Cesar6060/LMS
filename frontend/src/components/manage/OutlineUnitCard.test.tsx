import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { DndContext } from '@dnd-kit/core';
import { OutlineUnitCard, type OutlineUnit } from './OutlineUnitCard';

/**
 * Phase 66 — the instructor's lock control. The lock hides a unit from an
 * entire class, so the affordance has to be unambiguous: a labelled button
 * whose action flips, plus a visible badge on the card itself.
 */

function makeUnit(overrides: Partial<OutlineUnit> = {}): OutlineUnit {
  return {
    id: 7,
    title: 'Variables',
    lessons: [],
    is_locked: false,
    ...overrides,
  };
}

function renderCard(unit: OutlineUnit, onToggleLock = vi.fn()) {
  render(
    <MemoryRouter>
      <DndContext>
        <OutlineUnitCard
          unit={unit}
          courseCode="VGD101"
          collapsed
          quizzes={[]}
          onToggleCollapse={vi.fn()}
          onRenameUnit={vi.fn()}
          onDeleteUnit={vi.fn()}
          onRenameLesson={vi.fn()}
          onDeleteLesson={vi.fn()}
          onDeleteQuiz={vi.fn()}
          onAddLesson={vi.fn()}
          onAddQuiz={vi.fn()}
          onToggleLock={onToggleLock}
        />
      </DndContext>
    </MemoryRouter>
  );
  return onToggleLock;
}

describe('OutlineUnitCard lock toggle', () => {
  it('offers to lock an unlocked unit and shows no badge', () => {
    const onToggleLock = renderCard(makeUnit());

    expect(screen.queryByTestId('unit-locked-badge-7')).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', { name: 'Lock unit Variables from students' })
    );

    expect(onToggleLock).toHaveBeenCalledWith(7, true);
  });

  it('offers to unlock a locked unit and shows the Locked badge', () => {
    const onToggleLock = renderCard(makeUnit({ is_locked: true }));

    expect(screen.getByTestId('unit-locked-badge-7')).toHaveTextContent('Locked');

    fireEvent.click(
      screen.getByRole('button', { name: 'Unlock unit Variables for students' })
    );

    expect(onToggleLock).toHaveBeenCalledWith(7, false);
  });
});
