import { Link, useNavigate } from 'react-router';
import { LogOut, User, Gamepad2, Settings } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { NotificationBell } from '@/components/notifications/NotificationBell';

export function Header() {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 items-center px-4">
        <Link to="/" className="flex items-center space-x-2">
          <Gamepad2 className="h-6 w-6" />
          <span className="font-bold">GameDev Platform</span>
        </Link>

        <nav className="ml-auto flex items-center space-x-4">
          {isAuthenticated ? (
            <>
              <Link to="/dashboard">
                <Button variant="ghost" size="sm">
                  Dashboard
                </Button>
              </Link>
              <Link to="/courses">
                <Button variant="ghost" size="sm">
                  Courses
                </Button>
              </Link>
              <NotificationBell />
              <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                {user?.preferences?.avatar_url ? (
                  <img
                    src={user.preferences.avatar_url}
                    alt="Avatar"
                    className="h-6 w-6 rounded-full object-cover"
                  />
                ) : (
                  <User className="h-4 w-4" />
                )}
                <span>{user?.first_name || user?.email}</span>
                {user?.is_instructor && (
                  <span className="rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
                    Instructor
                  </span>
                )}
              </div>
              <Link to="/settings">
                <Button variant="ghost" size="sm" title="Settings">
                  <Settings className="h-4 w-4" />
                </Button>
              </Link>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  Login
                </Button>
              </Link>
              <Link to="/register">
                <Button size="sm">Register</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
