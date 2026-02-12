import React, { createContext, useContext, useMemo, useState } from 'react';
import { AuthAPI } from '../services/api';

type AuthCtx = {
  user: string | null;
  login: (email: string, password: string, code?: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
};

const Ctx = createContext<AuthCtx | undefined>(undefined);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [user, setUser] = useState<string | null>(localStorage.getItem('user_email'));

  const login = async (email: string, password: string, code?: string) => {
    const device = localStorage.getItem('device_fingerprint') || crypto.randomUUID();
    localStorage.setItem('device_fingerprint', device);
    const { data } = await AuthAPI.login(email, password, device);
    if (code) await AuthAPI.verify2FA(code);
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('user_email', email);
    setUser(email);
  };

  const register = async (email: string, password: string) => {
    await AuthAPI.register(email, password);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_email');
    setUser(null);
  };

  const value = useMemo(() => ({ user, login, register, logout, isAuthenticated: Boolean(user) }), [user]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
};
