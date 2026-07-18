import { useState, useRef, useEffect } from 'react';
import { quizzesService } from '@/services/quizzes';
import { Loader2 } from 'lucide-react';

interface EditableGradeCellProps {
  quizId: number;
  studentId: number;
  currentPoints: number | null;
  maxPoints: number;
  status: string;
  onUpdate: (newPoints: number) => void;
}

export function EditableGradeCell({
  quizId,
  studentId,
  currentPoints,
  maxPoints,
  status,
  onUpdate,
}: EditableGradeCellProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleClick = () => {
    setInputValue(currentPoints?.toString() ?? '');
    setError('');
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setError('');
    setInputValue('');
  };

  const handleSubmit = async () => {
    // If input is empty or unchanged, just cancel
    const trimmedValue = inputValue.trim();
    if (trimmedValue === '' || trimmedValue === (currentPoints?.toString() ?? '')) {
      handleCancel();
      return;
    }

    const points = parseInt(trimmedValue, 10);

    if (isNaN(points)) {
      setError('Enter a number');
      return;
    }

    if (points < 0 || points > maxPoints) {
      setError(`0-${maxPoints}`);
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      await quizzesService.quickGradeQuiz(quizId, studentId, points);
      onUpdate(points);
      setIsEditing(false);
    } catch (err) {
      console.error('Quick grade failed:', err);
      setError('Failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  const handleBlur = () => {
    if (!isSubmitting) {
      handleSubmit();
    }
  };

  // Editing mode
  if (isEditing) {
    return (
      <div className="relative">
        <input
          ref={inputRef}
          type="number"
          min="0"
          max={maxPoints}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          disabled={isSubmitting}
          className={`w-16 px-2 py-1 text-center text-sm border rounded focus:outline-none focus:ring-2 focus:ring-primary ${
            error ? 'border-red-500' : 'border-input'
          }`}
        />
        {isSubmitting && (
          <Loader2 className="absolute right-1 top-1/2 -translate-y-1/2 h-3 w-3 animate-spin" />
        )}
        {error && (
          <div className="absolute top-full left-0 text-xs text-red-500 whitespace-nowrap">
            {error}
          </div>
        )}
      </div>
    );
  }

  // Display mode: a cell is either a score or empty
  const isGraded = status === 'graded' && currentPoints !== null;
  const displayValue = isGraded ? `${currentPoints}/${maxPoints}` : '-';
  const bgColor = isGraded ? 'bg-emerald-50 dark:bg-emerald-950' : '';

  return (
    <div
      onClick={handleClick}
      className={`px-2 py-1 rounded text-sm cursor-pointer hover:ring-2 hover:ring-primary/50 ${bgColor}`}
      title="Click to edit grade"
    >
      {displayValue}
    </div>
  );
}
