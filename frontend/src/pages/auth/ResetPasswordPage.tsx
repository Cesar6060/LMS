import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Gamepad2, Loader2, CheckCircle } from 'lucide-react';
import authService from '@/services/auth';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const uid = searchParams.get('uid') || '';
  const token = searchParams.get('token') || '';

  const [password1, setPassword1] = useState('');
  const [password2, setPassword2] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (password1 !== password2) {
      setError('Passwords do not match');
      return;
    }

    if (password1.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsLoading(true);

    try {
      await authService.resetPassword(uid, token, password1, password2);
      setIsSuccess(true);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { token?: string[]; uid?: string[]; new_password1?: string[]; new_password2?: string[]; detail?: string } } };
      if (error.response?.data?.token) {
        setError('This reset link is invalid or has expired. Please request a new one.');
      } else if (error.response?.data?.uid) {
        setError('This reset link is invalid. Please request a new one.');
      } else if (error.response?.data?.new_password1) {
        setError(error.response.data.new_password1[0]);
      } else if (error.response?.data?.new_password2) {
        setError(error.response.data.new_password2[0]);
      } else if (error.response?.data?.detail) {
        setError(error.response.data.detail);
      } else {
        setError('Failed to reset password. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Show error if no uid or token provided
  if (!uid || !token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/50 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-1 text-center">
            <div className="flex justify-center mb-4">
              <Gamepad2 className="h-12 w-12 text-destructive" />
            </div>
            <CardTitle className="text-2xl">Invalid Reset Link</CardTitle>
            <CardDescription>
              This password reset link is invalid or incomplete.
            </CardDescription>
          </CardHeader>
          <CardFooter className="flex flex-col space-y-4">
            <Link to="/forgot-password" className="w-full">
              <Button className="w-full">Request New Reset Link</Button>
            </Link>
            <Link
              to="/login"
              className="text-sm text-muted-foreground hover:text-primary text-center"
            >
              Back to login
            </Link>
          </CardFooter>
        </Card>
      </div>
    );
  }

  // Show success state
  if (isSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/50 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-1 text-center">
            <div className="flex justify-center mb-4">
              <CheckCircle className="h-12 w-12 text-green-500" />
            </div>
            <CardTitle className="text-2xl">Password Reset!</CardTitle>
            <CardDescription>
              Your password has been successfully reset. You can now log in with your new password.
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button className="w-full" onClick={() => navigate('/login')}>
              Go to Login
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/50 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <Gamepad2 className="h-12 w-12 text-primary" />
          </div>
          <CardTitle className="text-2xl">Reset your password</CardTitle>
          <CardDescription>
            Enter your new password below
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="password1" className="text-sm font-medium">
                New Password
              </label>
              <Input
                id="password1"
                type="password"
                placeholder="Enter new password"
                value={password1}
                onChange={(e) => setPassword1(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password2" className="text-sm font-medium">
                Confirm New Password
              </label>
              <Input
                id="password2"
                type="password"
                placeholder="Confirm new password"
                value={password2}
                onChange={(e) => setPassword2(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Reset Password
            </Button>
            <Link
              to="/login"
              className="text-sm text-muted-foreground hover:text-primary text-center"
            >
              Back to login
            </Link>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
