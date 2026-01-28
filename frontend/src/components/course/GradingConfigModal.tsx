import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService } from '@/services/courses';
import type { GradingConfig } from '@/types';
import { Loader2, Settings, X } from 'lucide-react';

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
      setConfig(data);
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-background rounded-lg shadow-lg w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Grading Weights
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground mb-4">
              Configure how grades are weighted. Weights must sum to 100%.
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Assignments Weight (%)
                </label>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={config.assignments_weight}
                  onChange={(e) => setConfig({
                    ...config,
                    assignments_weight: parseInt(e.target.value) || 0
                  })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Quizzes Weight (%)
                </label>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={config.quizzes_weight}
                  onChange={(e) => setConfig({
                    ...config,
                    quizzes_weight: parseInt(e.target.value) || 0
                  })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Participation Weight (%)
                </label>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={config.participation_weight}
                  onChange={(e) => setConfig({
                    ...config,
                    participation_weight: parseInt(e.target.value) || 0
                  })}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Based on lesson completion percentage
                </p>
              </div>

              <div className={`text-sm font-medium ${isValid ? 'text-green-600' : 'text-red-600'}`}>
                Total: {total}% {isValid ? '✓' : '(must equal 100%)'}
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-600 mt-4">{error}</p>
            )}

            <div className="flex gap-3 mt-6">
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
                  'Save'
                )}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
