import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import authService from '@/services/auth';

type VerificationStatus = 'loading' | 'success' | 'error';

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const key = searchParams.get('key') || '';

  const [status, setStatus] = useState<VerificationStatus>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    if (!key) {
      setStatus('error');
      setErrorMessage('No verification key provided. Please check your email link.');
      return;
    }

    const verifyEmail = async () => {
      try {
        await authService.verifyEmail(key);
        setStatus('success');
      } catch (err: unknown) {
        setStatus('error');
        const error = err as { response?: { data?: { detail?: string; key?: string[] } } };
        if (error.response?.data?.detail) {
          setErrorMessage(error.response.data.detail);
        } else if (error.response?.data?.key) {
          setErrorMessage('This verification link is invalid or has already been used.');
        } else {
          setErrorMessage('Email verification failed. The link may have expired.');
        }
      }
    };

    verifyEmail();
  }, [key]);

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/50 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-1 text-center">
            <div className="flex justify-center mb-4">
              <Loader2 className="h-12 w-12 text-primary animate-spin" />
            </div>
            <CardTitle className="text-2xl">Verifying your email...</CardTitle>
            <CardDescription>
              Please wait while we verify your email address.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/50 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-1 text-center">
            <div className="flex justify-center mb-4">
              <CheckCircle className="h-12 w-12 text-green-500" />
            </div>
            <CardTitle className="text-2xl">Email Verified!</CardTitle>
            <CardDescription>
              Your email has been successfully verified. You can now log in to your account.
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Link to="/login" className="w-full">
              <Button className="w-full">Go to Login</Button>
            </Link>
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
            <XCircle className="h-12 w-12 text-destructive" />
          </div>
          <CardTitle className="text-2xl">Verification Failed</CardTitle>
          <CardDescription>{errorMessage}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center">
            If you're having trouble, try requesting a new verification email after logging in.
          </p>
        </CardContent>
        <CardFooter className="flex flex-col space-y-4">
          <Link to="/login" className="w-full">
            <Button className="w-full">Go to Login</Button>
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
