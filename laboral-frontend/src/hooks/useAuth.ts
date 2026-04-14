import { useState, useEffect, useCallback } from 'react';
import { authAPI } from '../services/api';
import type { User } from '../types';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('laboral_token')
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedUser = localStorage.getItem('laboral_user');
    if (token && savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('laboral_user');
      }
    } else if (token) {
      authAPI.me()
        .then((res) => {
          setUser(res.data);
          localStorage.setItem('laboral_user', JSON.stringify(res.data));
        })
        .catch(() => {
          localStorage.removeItem('laboral_token');
          localStorage.removeItem('laboral_user');
          setToken(null);
        });
    }
    setLoading(false);
  }, [token]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await authAPI.login({ username, password });
    const { access_token, user: userData } = res.data;
    localStorage.setItem('laboral_token', access_token);
    localStorage.setItem('laboral_user', JSON.stringify(userData));
    setToken(access_token);
    setUser(userData);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('laboral_token');
    localStorage.removeItem('laboral_user');
    setToken(null);
    setUser(null);
  }, []);

  return { user, token, loading, login, logout, isAuthenticated: !!token };
}
