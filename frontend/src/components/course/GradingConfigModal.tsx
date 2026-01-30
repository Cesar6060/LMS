import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import type { GradingConfig } from '@/types';
import { Loader2, X, Scale } from 'lucide-react';

interface GradingConfigModalProps {
  courseCode: string;
  isOpen: boolean;
  onClose: () => void;
}

export function GradingConfigModal({ courseCode, isOpen, onClose }: GradingConfigModalProps) {
  const [config, setConfig] = useState<GradingConfig>({
    assignments_weight: 50,
    quizzes_weight: 50,
    participation_weight: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadConfig();
    }
  }, [isOpen, courseCode]);

  const loadConfig = async () => {
    try {
      setIsLoading(true);
      const data = await courseService.getGradingConfig(courseCode);
      setConfig({
        assignments_weight: Number(data.assignments_weight) || 0,
        quizzes_weight: Number(data.quizzes_weight) || 0,
        participation_weight: Number(data.participation_weight) || 0,
      });
    } catch (err) {
      console.error('Failed to load config:', err);
      setError('Failed to load grading configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const total = config.assignments_weight + config.quizzes_weight + config.participation_weight;
  const isValid = total === 100;

  const handleSave = async () => {
    if (!isValid) return;

    setIsSaving(true);
    setError('');

    try {
      await courseService.updateGradingConfig(courseCode, config);
      onClose();
    } catch (err) {
      console.error('Failed to save config:', err);
      setError('Failed to save. Weights must sum to 100%.');
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
              <p className="text-xs text-muted-foreground">Configure category weights</p>
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
                {/* Assignments */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium">Assignments</label>
                    <span className="text-sm tabular-nums font-semibold">{config.assignments_weight}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={config.assignments_weight}
                    onChange={(e) => setConfig({ ...config, assignments_weight: Number(e.target.value) })}
                    className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-110"
                  />
                </div>

                {/* Quizzes */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium">Quizzes</label>
                    <span className="text-sm tabular-nums font-semibold">{config.quizzes_weight}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={config.quizzes_weight}
                    onChange={(e) => setConfig({ ...config, quizzes_weight: Number(e.target.value) })}
                    className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-110"
                  />
                </div>

                {/* Participation */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-sm font-medium">Participation</label>
                    <span className="text-sm tabular-nums font-semibold">{config.participation_weight}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={config.participation_weight}
                    onChange={(e) => setConfig({ ...config, participation_weight: Number(e.target.value) })}
                    className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-110"
                  />
                  <p className="text-xs text-muted-foreground mt-1.5">Based on lesson completion</p>
                </div>
              </div>

              {/* Total */}
              <div className={`mt-6 p-3 rounded-lg border ${
                isValid
                  ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-600 dark:text-emerald-400'
                  : 'bg-red-500/5 border-red-500/20 text-red-600 dark:text-red-400'
              }`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Total</span>
                  <span className="text-sm font-bold tabular-nums">
                    {total}%
                    {!isValid && <span className="font-normal ml-1">(must equal 100%)</span>}
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
              disabled={!isValid || isSaving}
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
