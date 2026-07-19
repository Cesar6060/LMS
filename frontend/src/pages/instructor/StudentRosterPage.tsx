import { useState, useEffect } from 'react';
import { useParams } from 'react-router';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService, type RosterStudent } from '@/services/courses';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/PageContainer';
import { BackLink } from '@/components/layout/BackLink';
import { CourseToolsNav } from '@/components/instructor/CourseToolsNav';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import {
  Mail, Users, AlertCircle, Trash2,
  Search, CheckCircle, Clock, AlertTriangle
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/Dialog';

type SortField = 'name' | 'email' | 'enrolled_at' | 'last_activity_at' | 'progress';
type SortDirection = 'asc' | 'desc';

export function StudentRosterPage() {
  const { code } = useParams<{ code: string }>();

  const [students, setStudents] = useState<RosterStudent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);

  // Search and sort
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Invite modal
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteSuccess, setInviteSuccess] = useState('');
  const [inviteError, setInviteError] = useState('');

  // Remove student dialog
  const [removeStudent, setRemoveStudent] = useState<RosterStudent | null>(null);
  const [isRemoving, setIsRemoving] = useState(false);

  useEffect(() => {
    if (code) {
      loadRoster();
    }
  }, [code]);

  const loadRoster = async () => {
    try {
      setIsLoading(true);
      const data = await courseService.getStudentRoster(code!);
      setStudents(data);
    } catch (err) {
      if (isForbidden(err)) {
        setForbidden(true);
      } else {
        setError('Failed to load student roster');
        console.error(err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleSendInvite = async () => {
    if (!inviteEmail.trim()) return;

    try {
      setInviteLoading(true);
      setInviteError('');
      setInviteSuccess('');
      const result = await courseService.sendCourseInvite(code!, inviteEmail.trim());
      setInviteSuccess(result.message);
      setInviteEmail('');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { error?: string } } };
      setInviteError(error.response?.data?.error || 'Failed to send invitation');
    } finally {
      setInviteLoading(false);
    }
  };

  const closeInviteModal = () => {
    setShowInviteModal(false);
    setInviteEmail('');
    setInviteSuccess('');
    setInviteError('');
  };

  const handleRemoveStudent = async () => {
    if (!removeStudent) return;

    try {
      setIsRemoving(true);
      await courseService.removeStudent(code!, removeStudent.id);
      setRemoveStudent(null);
      loadRoster();
    } catch (err) {
      console.error('Remove student failed:', err);
    } finally {
      setIsRemoving(false);
    }
  };


  // Filter and sort students
  const filteredStudents = students
    .filter((s) => {
      if (!searchQuery) return true;
      const query = searchQuery.toLowerCase();
      return (
        s.email.toLowerCase().includes(query) ||
        s.first_name.toLowerCase().includes(query) ||
        s.last_name.toLowerCase().includes(query)
      );
    })
    .sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'name':
          comparison = `${a.last_name} ${a.first_name}`.localeCompare(`${b.last_name} ${b.first_name}`);
          break;
        case 'email':
          comparison = a.email.localeCompare(b.email);
          break;
        case 'enrolled_at':
          comparison = new Date(a.enrolled_at).getTime() - new Date(b.enrolled_at).getTime();
          break;
        case 'last_activity_at': {
          const aTime = a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0;
          const bTime = b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0;
          comparison = aTime - bTime;
          break;
        }
        case 'progress':
          comparison = a.progress_percentage - b.progress_percentage;
          break;
      }
      return sortDirection === 'asc' ? comparison : -comparison;
    });

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return 'Never';

    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    const diffWeeks = Math.floor(diffDays / 7);
    const diffMonths = Math.floor(diffDays / 30);

    if (diffSeconds < 60) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
    if (diffWeeks < 4) return `${diffWeeks} week${diffWeeks === 1 ? '' : 's'} ago`;
    if (diffMonths < 12) return `${diffMonths} month${diffMonths === 1 ? '' : 's'} ago`;

    return formatDate(dateStr);
  };

  const getActivityBadge = (student: RosterStudent) => {
    if (!student.last_activity_at) {
      return (
        <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
          <Clock className="h-3 w-3" />
          Never Active
        </span>
      );
    }
    if (student.is_inactive) {
      return (
        <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300">
          <AlertTriangle className="h-3 w-3" />
          Inactive
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">
        <CheckCircle className="h-3 w-3" />
        Active
      </span>
    );
  };

  if (isLoading) {
    return (
      <PageContainer>
        <div className="mb-6">
          <Skeleton className="h-4 w-32 mb-4" />
          <Skeleton className="h-8 w-64 mb-2" />
        </div>
        <Skeleton className="h-64 w-full" />
      </PageContainer>
    );
  }

  if (forbidden) {
    return <AccessDenied />;
  }

  if (error) {
    return (
      <PageContainer>
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Error</h3>
            <p className="text-muted-foreground mb-4">{error}</p>
            <BackLink to={`/instructor/courses/${code}/manage`} label="Manage Course" />
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      {/* Course tools sub-nav */}
      <CourseToolsNav courseCode={code!} className="mb-6" />

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Users className="h-6 w-6" />
              Student Roster
            </h1>
            <p className="text-muted-foreground">{students.length} students enrolled</p>
          </div>

          <Button onClick={() => setShowInviteModal(true)}>
            <Mail className="h-4 w-4 mr-2" />
            Invite Student
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="mb-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search students..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3 mb-6">
        <Card>
          <CardContent className="py-4">
            <div className="text-2xl font-bold">{students.length}</div>
            <p className="text-sm text-muted-foreground">Total Students</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4">
            <div className="text-2xl font-bold text-green-600">
              {students.filter(s => !s.is_inactive).length}
            </div>
            <p className="text-sm text-muted-foreground">Active (last 7 days)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4">
            <div className="text-2xl font-bold text-red-600">
              {students.filter(s => s.is_inactive).length}
            </div>
            <p className="text-sm text-muted-foreground">Inactive (7+ days)</p>
          </CardContent>
        </Card>
      </div>

      {/* Student Table */}
      {filteredStudents.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">
              {searchQuery ? 'No matching students' : 'No students enrolled yet'}
            </h3>
            <p className="text-muted-foreground">
              {searchQuery
                ? 'Try a different search term.'
                : 'Share the enrollment code or send an email invitation.'}
            </p>
            {!searchQuery && (
              <Button className="mt-4" onClick={() => setShowInviteModal(true)}>
                <Mail className="h-4 w-4 mr-2" />
                Invite Student
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    {(
                      [
                        { field: 'name', label: 'Name', align: 'left' },
                        { field: 'email', label: 'Email', align: 'left' },
                        { field: 'enrolled_at', label: 'Enrolled', align: 'left' },
                        { field: 'last_activity_at', label: 'Last Active', align: 'left' },
                        { field: 'progress', label: 'Progress', align: 'center' },
                      ] as { field: SortField; label: string; align: 'left' | 'center' }[]
                    ).map(({ field, label, align }) => (
                      <th
                        key={field}
                        className={`p-3 font-medium hover:bg-muted ${
                          align === 'center' ? 'text-center' : 'text-left'
                        }`}
                        aria-sort={
                          sortField === field
                            ? sortDirection === 'asc'
                              ? 'ascending'
                              : 'descending'
                            : undefined
                        }
                      >
                        <button
                          type="button"
                          onClick={() => handleSort(field)}
                          className={`w-full p-0 font-medium ${
                            align === 'center' ? 'text-center' : 'text-left'
                          }`}
                        >
                          {label} {sortField === field && (sortDirection === 'asc' ? '↑' : '↓')}
                        </button>
                      </th>
                    ))}
                    <th className="text-center p-3 font-medium">Status</th>
                    <th className="text-center p-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStudents.map((student) => (
                    <tr key={student.id} className="border-b hover:bg-muted/30">
                      <td className="p-3 font-medium">
                        {student.first_name} {student.last_name}
                      </td>
                      <td className="p-3 text-muted-foreground">{student.email}</td>
                      <td className="p-3">{formatDate(student.enrolled_at)}</td>
                      <td className="p-3">{formatRelativeTime(student.last_activity_at)}</td>
                      <td className="p-3 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary"
                              style={{ width: `${student.progress_percentage}%` }}
                            />
                          </div>
                          <span className="text-xs">{student.progress_percentage}%</span>
                        </div>
                      </td>
                      <td className="p-3 text-center">
                        {getActivityBadge(student)}
                      </td>
                      <td className="p-3 text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setRemoveStudent(student)}
                          className="text-destructive hover:text-destructive"
                          aria-label={`Remove ${student.first_name} ${student.last_name}`}
                          title="Remove student"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Invite Student Modal */}
      <Dialog open={showInviteModal} onOpenChange={closeInviteModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite Student</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <p className="text-sm text-muted-foreground">
              Send an email invitation with the course enrollment code.
            </p>

            {inviteSuccess && (
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3 flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-600" />
                <p className="text-sm text-green-700 dark:text-green-300">{inviteSuccess}</p>
              </div>
            )}

            {inviteError && (
              <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-destructive" />
                <p className="text-sm text-destructive">{inviteError}</p>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="invite-email" className="text-sm font-medium">
                Email Address
              </label>
              <Input
                id="invite-email"
                type="email"
                placeholder="student@example.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && inviteEmail.trim()) {
                    handleSendInvite();
                  }
                }}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeInviteModal}>
              Close
            </Button>
            <Button
              onClick={handleSendInvite}
              disabled={!inviteEmail.trim() || inviteLoading}
            >
              <Mail className="h-4 w-4 mr-2" />
              {inviteLoading ? 'Sending...' : 'Send Invitation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Student Dialog */}
      <ConfirmDialog
        open={!!removeStudent}
        onOpenChange={(open) => {
          if (!open) setRemoveStudent(null);
        }}
        title="Remove Student"
        confirmLabel="Remove Student"
        loadingLabel="Removing..."
        onConfirm={handleRemoveStudent}
        isLoading={isRemoving}
      >
        Are you sure you want to remove{' '}
        <span className="font-medium text-foreground">
          {removeStudent?.first_name} {removeStudent?.last_name}
        </span>{' '}
        from this course? Their grades will be preserved.
      </ConfirmDialog>
    </PageContainer>
  );
}
