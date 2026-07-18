import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import { Loader2, X, Scale } from 'lucide-react';

interface GradingConfigModalProps {
  courseCode: string;
  isOpen: boolean;
  onClose: () => void;
}

const SLIDER_CLASS = 'w-full h-2 bg-muted rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-110';

const clampWeight = (value: number): number => Math.min(100, Math.max(0, Math.round(value)));

export function GradingConfigModal({ courseCode, isOpen, onClose }: GradingConfigModalProps) {
  // Single source of truth: participation is always 100 - quizzes
  const [quizzesWeight, setQuizzesWeight] = useState(50);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const participationWeight = 100 - quizzesWeight;

  useEffect(() => {
    if (isOpen) {
      loadConfig();
    }
  }, [isOpen, courseCode]);

  const loadConfig = async () => {
    try {
      setIsLoading(true);
      setError('');
      const data = await courseService.getGradingConfig(courseCode);
      setQuizzesWeight(clampWeight(Number(data.quizzes_weight) || 0));
    } catch (err) {
      console.error('Failed to load config:', err);
      setError('Failed to load grading configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError('');

    try {
      await courseService.updateGradingConfig(courseCode, {
        quizzes_weight: quizzesWeight,
        participation_weight: participationWeight,
      });
      onClose();
    } catch (err) {
      console.error('Failed to save config:', err);
      setError('Failed to save grading weights.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-card border border-border rounded-xl shadow-2xl w-full max-w-md overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-muted/30">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Scale className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold">Grade Weights</h2>
              <p className="text-xs text-muted-foreground">Quizzes and participation always total 100%</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              <div className="space-y-5">
                {/* Quizzes */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium">Quizzes</label>
                    <span className="text-sm tabular-nums font-semibold">{quizzesWeight}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={quizzesWeight}
                    onChange={(e) => setQuizzesWeight(clampWeight(Number(e.target.value)))}
                    className={SLIDER_CLASS}
                  />
                </div>

                {/* Participation */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium">Participation</label>
                    <span className="text-sm tabular-nums font-semibold">{participationWeight}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={participationWeight}
                    onChange={(e) => setQuizzesWeight(clampWeight(100 - Number(e.target.value)))}
                    className={SLIDER_CLASS}
                  />
                  <p className="text-xs text-muted-foreground mt-1.5">Based on lesson completion</p>
                </div>
              </div>

              {/* Total */}
              <div className="mt-6 p-3 rounded-lg border bg-emerald-500/5 border-emerald-500/20 text-emerald-600 dark:text-emerald-400">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Total</span>
                  <span className="text-sm font-bold tabular-nums">
                    {quizzesWeight + participationWeight}%
                  </span>
                </div>
              </div>

              {error && (
                <p className="text-sm text-red-600 mt-4">{error}</p>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {!isLoading && (
          <div className="flex gap-3 px-6 py-4 border-t border-border bg-muted/30">
            <Button variant="outline" onClick={onClose} className="flex-1">
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isSaving}
              className="flex-1"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
