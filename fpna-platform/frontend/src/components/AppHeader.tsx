import React, { useState, useEffect, useRef } from 'react';
import { Bell, ChevronDown, LogOut, Check, Loader2, Sun, Moon, Settings, User } from 'lucide-react';
import { notificationsAPI } from '../services/api';

export interface NotificationItem {
  id: number;
  type: string;
  budget_id: number | null;
  budget_code: string | null;
  plan_id?: number | null;
  plan_code?: string | null;
  link_step?: number | null;
  actor_username: string | null;
  message: string;
  read_at: string | null;
  created_at: string;
}

interface AppHeaderProps {
  username: string;
  fullName?: string;
  roles: string[];
  onLogout: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onNotificationClick?: (notification: NotificationItem) => void;
}

const AppHeader: React.FC<AppHeaderProps> = ({ username, fullName, roles, onLogout, theme, onToggleTheme, onNotificationClick }) => {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [loadingNotif, setLoadingNotif] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  const fetchNotifications = async () => {
    try {
      const [listRes, countRes] = await Promise.all([
        notificationsAPI.list(false),
        notificationsAPI.unreadCount(),
      ]);
      setNotifications(listRes.items || []);
      setUnreadCount(countRes.count || 0);
    } catch {
      setNotifications([]);
      setUnreadCount(0);
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        notifRef.current && !notifRef.current.contains(e.target as Node) &&
        userRef.current && !userRef.current.contains(e.target as Node)
      ) {
        setShowNotifications(false);
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMarkAsRead = async (id: number) => {
    setLoadingNotif(true);
    try {
      await notificationsAPI.markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } finally {
      setLoadingNotif(false);
    }
  };

  const handleMarkAllRead = async () => {
    setLoadingNotif(true);
    try {
      await notificationsAPI.markAllAsRead();
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() }))
      );
      setUnreadCount(0);
    } finally {
      setLoadingNotif(false);
    }
  };

  const isDark = theme === 'dark';
  const displayName = fullName || username;
  const roleLabel = roles.length > 0 ? roles[0] : 'User';
  const initials = displayName.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();

  const dropdownCls = `absolute right-0 mt-2 rounded-xl shadow-card-lg border z-50 py-1.5 overflow-hidden ${
    isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
  }`;

  return (
    <header
      className={`sticky top-0 z-40 bg-glass border-b flex items-center justify-between px-5 transition-colors ${
        isDark
          ? 'bg-slate-900/95 border-slate-800 text-slate-100'
          : 'bg-white/95 border-slate-200 text-slate-900'
      }`}
      style={{ height: 'var(--header-height, 56px)' }}
    >
      {/* Left: Logo + wordmark */}
      <div className="flex items-center gap-3 select-none">
        <div className="w-8 h-8 rounded-lg brand-gradient flex items-center justify-center shadow-sm shrink-0">
          <span className="text-[11px] font-bold tracking-wide text-white">FP</span>
        </div>
        <div className="hidden sm:flex flex-col leading-none">
          <span className={`text-sm font-bold tracking-tight ${isDark ? 'text-slate-50' : 'text-slate-900'}`}>
            FPNA Platform
          </span>
          <span className={`text-[10px] font-medium tracking-wide uppercase ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Financial Planning &amp; Analytics
          </span>
        </div>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-1.5">
        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          className={`btn-icon transition-fast ${isDark ? 'text-slate-400 hover:bg-slate-800 hover:text-amber-400' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'}`}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label="Toggle theme"
        >
          {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => { setShowNotifications(!showNotifications); setShowUserMenu(false); }}
            className={`btn-icon relative transition-fast ${isDark ? 'text-slate-400 hover:bg-slate-800 hover:text-slate-100' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'}`}
            aria-label="Notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-primary-600 text-white text-[9px] font-bold rounded-full flex items-center justify-center shadow">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {showNotifications && (
            <div className={`${dropdownCls} w-80 animate-fade-in`}>
              <div className={`px-4 py-2.5 border-b flex justify-between items-center ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
                <span className={`font-semibold text-sm ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Notifications</span>
                {unreadCount > 0 && (
                  <button onClick={handleMarkAllRead} disabled={loadingNotif} className="text-[11px] text-primary-500 hover:text-primary-400 font-medium">
                    Mark all read
                  </button>
                )}
              </div>
              <div className="max-h-72 overflow-y-auto">
                {loadingNotif && notifications.length === 0 ? (
                  <div className="p-6 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>
                ) : notifications.length === 0 ? (
                  <div className={`p-6 text-center text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No notifications</div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      className={`px-4 py-3 cursor-pointer border-b last:border-0 transition-fast ${
                        isDark
                          ? `${!n.read_at ? 'bg-primary-950/40' : ''} border-slate-800 hover:bg-slate-800`
                          : `${!n.read_at ? 'bg-primary-50/60' : ''} border-slate-50 hover:bg-slate-50`
                      }`}
                      onClick={() => { if (!n.read_at) handleMarkAsRead(n.id); if (onNotificationClick) onNotificationClick(n); }}
                    >
                      <div className="flex items-start gap-2">
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm leading-tight ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>{n.message}</p>
                          <p className={`text-[11px] mt-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                            {new Date(n.created_at).toLocaleString()}
                          </p>
                        </div>
                        {!n.read_at && (
                          <button onClick={(e) => { e.stopPropagation(); handleMarkAsRead(n.id); }} className={`p-1 rounded ${isDark ? 'hover:bg-slate-700' : 'hover:bg-slate-200'}`} title="Mark as read">
                            <Check className="w-3.5 h-3.5 text-primary-500" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className={`w-px h-5 mx-1 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`} />

        {/* User menu */}
        <div className="relative" ref={userRef}>
          <button
            onClick={() => { setShowUserMenu(!showUserMenu); setShowNotifications(false); }}
            className={`flex items-center gap-2.5 pl-2 pr-3 py-1.5 rounded-xl transition-fast ${
              isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100'
            } ${showUserMenu ? (isDark ? 'bg-slate-800' : 'bg-slate-100') : ''}`}
          >
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-bold text-white shrink-0 brand-gradient shadow-sm`}>
              {initials}
            </div>
            <div className="text-left hidden sm:block leading-tight">
              <p className={`text-[13px] font-semibold truncate max-w-[120px] ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>{displayName}</p>
              <p className={`text-[10px] font-medium uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{roleLabel}</p>
            </div>
            <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${showUserMenu ? 'rotate-180' : ''} ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
          </button>

          {showUserMenu && (
            <div className={`${dropdownCls} w-52 animate-fade-in`}>
              <div className={`px-4 py-3 border-b ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
                <p className={`font-semibold text-sm ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>{displayName}</p>
                <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>@{username}</p>
                {roles.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {roles.map((r) => (
                      <span key={r} className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${isDark ? 'bg-primary-900/50 text-primary-400' : 'bg-primary-50 text-primary-700'}`}>{r}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="py-1">
                <button className={`w-full flex items-center gap-2.5 px-4 py-2 text-sm transition-fast ${isDark ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-50'}`}>
                  <User className="w-4 h-4" /> Profile
                </button>
                <button className={`w-full flex items-center gap-2.5 px-4 py-2 text-sm transition-fast ${isDark ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-50'}`}>
                  <Settings className="w-4 h-4" /> Preferences
                </button>
              </div>
              <div className={`border-t py-1 ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
                <button
                  onClick={() => { setShowUserMenu(false); onLogout(); }}
                  className={`w-full flex items-center gap-2.5 px-4 py-2 text-sm font-medium transition-fast ${isDark ? 'text-red-400 hover:bg-red-950/30' : 'text-red-600 hover:bg-red-50'}`}
                >
                  <LogOut className="w-4 h-4" /> Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default AppHeader;
