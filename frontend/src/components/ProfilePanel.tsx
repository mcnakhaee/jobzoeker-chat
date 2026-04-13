import { useState, useEffect } from 'react';
import type { UserProfile } from '../types';
import { getProfile, updateProfile } from '../api/client';

export default function ProfilePanel() {
  const [profile, setProfile] = useState<UserProfile>({
    background: '',
    preferences: '',
    cover_letter_tone: 'professional',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {});
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      await updateProfile(profile);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // silently ignore — backend may not be running
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="profile-panel">
      <p className="panel-label">Profile</p>
      <p className="panel-hint">
        Used to personalise cover letters and filter job matches.
      </p>

      <div className="field">
        <label htmlFor="background">Background</label>
        <textarea
          id="background"
          placeholder="e.g. 5 years Python, data engineering background…"
          value={profile.background}
          rows={3}
          onChange={e => setProfile(p => ({ ...p, background: e.target.value }))}
        />
      </div>

      <div className="field">
        <label htmlFor="preferences">Preferences</label>
        <textarea
          id="preferences"
          placeholder="e.g. Remote, Amsterdam area, €70k+, no consultancy…"
          value={profile.preferences}
          rows={3}
          onChange={e => setProfile(p => ({ ...p, preferences: e.target.value }))}
        />
      </div>

      <div className="field">
        <label htmlFor="tone">Cover letter tone</label>
        <select
          id="tone"
          value={profile.cover_letter_tone}
          onChange={e => setProfile(p => ({ ...p, cover_letter_tone: e.target.value }))}
        >
          <option value="professional">Professional</option>
          <option value="friendly">Friendly</option>
          <option value="confident">Confident</option>
          <option value="concise">Concise</option>
        </select>
      </div>

      <button
        className={`save-btn${saved ? ' saved' : ''}`}
        onClick={handleSave}
        disabled={saving}
      >
        {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save profile'}
      </button>
    </div>
  );
}
