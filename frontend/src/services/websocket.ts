import { io, Socket } from 'socket.io-client';

type Handler = (payload: any) => void;

export class WSClient {
  private socket?: Socket;
  private handlers: Record<string, Set<Handler>> = {};

  connect(token: string) {
    this.socket = io(import.meta.env.VITE_WS_URL, {
      auth: { token },
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
    });

    this.socket.onAny((event, payload) => this.handlers[event]?.forEach((h) => h(payload)));
  }

  disconnect() {
    this.socket?.disconnect();
  }

  subscribe(topic: string) {
    this.socket?.emit('subscribe', { topic });
  }

  unsubscribe(topic: string) {
    this.socket?.emit('unsubscribe', { topic });
  }

  on(event: string, handler: Handler) {
    this.handlers[event] = this.handlers[event] || new Set();
    this.handlers[event].add(handler);
  }

  off(event: string, handler: Handler) {
    this.handlers[event]?.delete(handler);
  }
}
