import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { ApiError, api, post, setToken, getToken } from '../api/client';

export interface User {
  user_id: string; role: string; name: string; status: string; district: string | null;
  portal: string; permissions: string[]; must_change_password: boolean;
}
interface Ctx {
  user: User | null; loading: boolean;
  login: (officerId: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}
const AuthContext = createContext<Ctx>(null as unknown as Ctx);
export const useAuth = () => useContext(AuthContext);

// Officer roles only: beneficiaries use the mobile app.
export const PORTAL_ROLE: Record<string, string> = {
  '/dso': 'DSO', '/admin': 'SYSTEM_ADMIN', '/fps': 'FPS_OWNER', '/inspector': 'FIELD_FOOD_INSPECTOR', '/auditor': 'AUDITOR',
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(!!getToken());

  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); setLoading(false); return; }
    try { setUser(await api<User>('/api/v1/auth/me')); }
    catch (e) { if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setToken(null); setUser(null); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const login = async (officerId: string, password: string) => {
    const r = await post<{ access_token: string }>('/api/v1/auth/officer/login', { officer_id: officerId.trim(), password });
    setToken(r.access_token);
    const me = await api<User>('/api/v1/auth/me');
    setUser(me);
    return me;
  };
  const logout = async () => {
    try { await post('/api/v1/auth/logout'); } catch { /* token may already be invalid */ }
    setToken(null); setUser(null);
  };
  return <AuthContext.Provider value={{ user, loading, login, logout, refresh }}>{children}</AuthContext.Provider>;
}
