import { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { settingsService } from '@/services/settings';
import { useAuth } from '@/contexts/AuthContext';
import type { UserPreferences } from '@/types';
import {
  Settings, User, Bell, Loader2, Camera, Trash2, Check
} from 'lucide-react';
import { PageContainer } from '@/components/layout/PageContainer';

type TabType = 'profile' | 'notifications';

export function SettingsPage() {
  const { user, refreshUser } = useAuth();

  const [activeTab, setActiveTab] = useState<TabType>('profile');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);

  // Profile form state
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');

  // Avatar upload
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    if (user) {
      setFirstName(user.first_name || '');
      setLastName(user.last_name || '');
    }
  }, [user]);

  const loadSettings = async () => {
    try {
      setIsLoading(true);
      const data = await settingsService.getSettings();
      setPreferences(data);
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveProfile = async () => {
    setIsSaving(true);
    setSaveMessage('');
    try {
      await settingsService.updateProfile({ first_name: firstName, last_name: lastName });
      await refreshUser();
      setSaveMessage('Profile saved successfully');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (err) {
      console.error('Failed to save profile:', err);
      setSaveMessage('Failed to save profile');
    } finally {
      setIsSaving(false);
    }
  };

  const handleAvatarSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      alert('Image must be less than 5MB');
      return;
    }

    setIsUploadingAvatar(true);
    try {
      const updated = await settingsService.uploadAvatar(file);
      setPreferences(updated);
      await refreshUser();
    } catch (err) {
      console.error('Failed to upload avatar:', err);
      alert('Failed to upload avatar');
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const handleDeleteAvatar = async () => {
    if (!confirm('Are you sure you want to remove your avatar?')) return;

    setIsUploadingAvatar(true);
    try {
      const updated = await settingsService.deleteAvatar();
      setPreferences(updated);
      await refreshUser();
    } catch (err) {
      console.error('Failed to delete avatar:', err);
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const handleUpdatePreference = async (key: keyof UserPreferences, value: boolean | string) => {
    if (!preferences) return;

    // Optimistic update
    setPreferences(prev => prev ? { ...prev, [key]: value } : null);

    try {
      await settingsService.updateSettings({ [key]: value });
    } catch (err) {
      console.error('Failed to update preference:', err);
      // Revert on error
      loadSettings();
    }
  };

  const tabs = [
    { id: 'profile' as TabType, label: 'Profile', icon: User },
    { id: 'notifications' as TabType, label: 'Notifications', icon: Bell },
  ];

  if (isLoading) {
    return (
      <PageContainer maxWidth="max-w-4xl">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer maxWidth="max-w-4xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Settings className="h-8 w-8" />
          Settings
        </h1>
        <p className="text-muted-foreground mt-2">
          Manage your account settings and preferences
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="space-y-6">
          {/* Avatar */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Profile Picture</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-6">
                <div className="relative">
                  <div className="w-24 h-24 rounded-full bg-muted flex items-center justify-center overflow-hidden">
                    {preferences?.avatar_url ? (
                      <img
                        src={preferences.avatar_url}
                        alt="Avatar"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <User className="h-12 w-12 text-muted-foreground" />
                    )}
                  </div>
                  {isUploadingAvatar && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-full">
                      <Loader2 className="h-6 w-6 animate-spin text-white" />
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <input
                    type="file"
                    ref={fileInputRef}
                    className="hidden"
                    accept="image/*"
                    onChange={handleAvatarSelect}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploadingAvatar}
                  >
                    <Camera className="h-4 w-4 mr-2" />
                    Upload Photo
                  </Button>
                  {preferences?.avatar_url && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleDeleteAvatar}
                      disabled={isUploadingAvatar}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Remove
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Name */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Personal Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">First Name</label>
                  <Input
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="First name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Last Name</label>
                  <Input
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Last name"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Email</label>
                <Input value={user?.email || ''} disabled className="bg-muted" />
                <p className="text-xs text-muted-foreground mt-1">
                  Email cannot be changed
                </p>
              </div>
              <div className="flex items-center gap-4">
                <Button onClick={handleSaveProfile} disabled={isSaving}>
                  {isSaving ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4 mr-2" />
                  )}
                  Save Changes
                </Button>
                {saveMessage && (
                  <span className={`text-sm ${saveMessage.includes('Failed') ? 'text-destructive' : 'text-green-600'}`}>
                    {saveMessage}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && preferences && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Email Notifications</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              <ToggleSetting
                label="Course Announcements"
                description="Receive email notifications when instructors post announcements"
                checked={preferences.email_announcements}
                onChange={(v) => handleUpdatePreference('email_announcements', v)}
              />
              <ToggleSetting
                label="Grade Notifications"
                description="Receive email notifications when your assignments are graded"
                checked={preferences.email_grades}
                onChange={(v) => handleUpdatePreference('email_grades', v)}
              />
              {user?.is_instructor && (
                <ToggleSetting
                  label="Student Submissions"
                  description="Receive email notifications when students submit assignments"
                  checked={preferences.email_submissions}
                  onChange={(v) => handleUpdatePreference('email_submissions', v)}
                />
              )}
              <ToggleSetting
                label="Due Date Reminders"
                description="Receive email reminders before assignment due dates"
                checked={preferences.email_due_reminders}
                onChange={(v) => handleUpdatePreference('email_due_reminders', v)}
              />
            </div>
          </CardContent>
        </Card>
      )}

    </PageContainer>
  );
}

// Toggle Switch Component
function ToggleSetting({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-3 border-b last:border-0">
      <div>
        <p className="font-medium">{label}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          checked ? 'bg-primary' : 'bg-muted'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

