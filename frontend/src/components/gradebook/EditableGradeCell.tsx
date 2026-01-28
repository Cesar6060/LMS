import { useState, useRef, useEffect } from 'react';
import { assignmentService } from '@/services/assignments';
import { Loader2 } from 'lucide-react';

interface EditableGradeCellProps {
  itemId: number;
  itemType: 'assignment' | 'quiz';
  studentId: number;
  currentPoints: number | null;
  maxPoints: number;
  status: string;
  isLate: boolean;
  onUpdate: (newPoints: number) => void;
}

export function EditableGradeCell({
  itemId,
  itemType,
  studentId,
  currentPoints,
  maxPoints,
  status,
  isLate,
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

  // Only assignments can be quick-graded (quizzes are auto-graded)
  const canEdit = itemType === 'assignment';

  const handleClick = () => {
    if (!canEdit) return;
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
      await assignmentService.quickGrade(itemId, studentId, points);
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

  // Display mode
  const displayValue = status === 'graded' && currentPoints !== null
    ? `${currentPoints}/${maxPoints}`
    : status === 'submitted'
    ? 'Pending'
    : status === 'missing'
    ? 'Missing'
    : '-';

  const bgColor = status === 'graded'
    ? 'bg-emerald-50 dark:bg-emerald-950'
    : status === 'submitted'
    ? 'bg-sky-50 dark:bg-sky-950'
    : status === 'missing'
    ? 'bg-rose-50 dark:bg-rose-950'
    : '';

  return (
    <div
      onClick={handleClick}
      className={`px-2 py-1 rounded text-sm ${bgColor} ${
        canEdit ? 'cursor-pointer hover:ring-2 hover:ring-primary/50' : ''
      } ${isLate ? 'ring-1 ring-amber-400' : ''}`}
      title={canEdit ? 'Click to edit grade' : 'Quiz grades are auto-calculated'}
    >
      {displayValue}
      {isLate && <span className="ml-1 text-amber-600 text-xs">L</span>}
    </div>
  );
}
