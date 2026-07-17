import { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService } from '@/services/courses';
import { Loader2, ChevronLeft } from 'lucide-react';

export function CreateCoursePage() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    code: '',
    title: '',
    description: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const course = await courseService.createCourse(formData);
      navigate(`/instructor/courses/${course.code}/manage`);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { code?: string[]; title?: string[]; detail?: string } } };
      if (error.response?.data?.code) {
        setError(`Course code: ${error.response.data.code[0]}`);
      } else if (error.response?.data?.title) {
        setError(`Title: ${error.response.data.title[0]}`);
      } else if (error.response?.data?.detail) {
        setError(error.response.data.detail);
      } else {
        setError('Failed to create course. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <Link to="/courses">
        <Button variant="ghost" size="sm" className="mb-6">
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back to Courses
        </Button>
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>Create a New Course</CardTitle>
          <CardDescription>
            Fill in the details below to create a new course. You can add units and lessons after creation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="code" className="text-sm font-medium">
                Course Code
              </label>
              <Input
                id="code"
                type="text"
                placeholder="e.g., GD101"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                maxLength={10}
                required
                className="font-mono"
              />
              <p className="text-xs text-muted-foreground">
                A unique identifier for your course (max 10 characters).
              </p>
            </div>

            <div className="space-y-2">
              <label htmlFor="title" className="text-sm font-medium">
                Course Title
              </label>
              <Input
                id="title"
                type="text"
                placeholder="e.g., Introduction to Game Development"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                maxLength={200}
                required
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="description" className="text-sm font-medium">
                Description
              </label>
              <textarea
                id="description"
                placeholder="Describe what students will learn in this course..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={4}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>

            <div className="flex gap-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/courses')}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create Course
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
