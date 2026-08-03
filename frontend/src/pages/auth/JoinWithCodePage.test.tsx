import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { JoinWithCodePage } from './JoinWithCodePage';

const mockJoinWithCode = vi.hoisted(() => vi.fn());

vi.mock('@/services/invites', () => ({
  inviteService: { joinWithCode: mockJoinWithCode },
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/join']}>
      <Routes>
        <Route path="/join" element={<JoinWithCodePage />} />
        <Route path="/invite/:token" element={<div>accept page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

function fillAndSubmit(code: string, email: string) {
  fireEvent.change(screen.getByLabelText(/class code/i), { target: { value: code } });
  fireEvent.change(screen.getByLabelText(/your email/i), { target: { value: email } });
  fireEvent.click(screen.getByRole('button', { name: /continue/i }));
}

describe('JoinWithCodePage', () => {
  beforeEach(() => {
    mockJoinWithCode.mockReset();
  });

  it('renders the generic error the API returns for bad input', async () => {
    mockJoinWithCode.mockRejectedValue({
      response: {
        status: 400,
        data: { detail: "That code and email don't match an open invitation." },
      },
    });

    renderPage();
    fillAndSubmit('WRONG123', 'nobody@example.com');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "That code and email don't match an open invitation."
    );
    expect(screen.queryByText('accept page')).not.toBeInTheDocument();
  });

  it('navigates to the accept page on a successful redemption', async () => {
    mockJoinWithCode.mockResolvedValue({
      token: 'tok-abc123',
      course_title: 'Intro to Robotics',
      course_code: 'ROB101',
    });

    renderPage();
    fillAndSubmit('abcd-2345', 'student@example.com');

    expect(await screen.findByText('accept page')).toBeInTheDocument();
    await waitFor(() =>
      expect(mockJoinWithCode).toHaveBeenCalledWith('abcd-2345', 'student@example.com')
    );
  });
});
