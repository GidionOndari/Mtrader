import React, { createContext, useContext, useEffect, useMemo } from 'react';
import { WSClient } from '../services/websocket';
import { useAuth } from './AuthContext';

const Ctx = createContext<WSClient | undefined>(undefined);

export const WebSocketProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const client = useMemo(() => new WSClient(), []);

  useEffect(() => {
    if (isAuthenticated) {
      const token = localStorage.getItem('access_token') || '';
      client.connect(token);
      return () => client.disconnect();
    }
  }, [client, isAuthenticated]);

  return <Ctx.Provider value={client}>{children}</Ctx.Provider>;
};

export const useWS = () => {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useWS must be inside WebSocketProvider');
  return ctx;
};
