import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const latency = new Trend('ws_message_latency');
const connectSuccess = new Rate('ws_connect_success');
const errorRate = new Rate('ws_error_rate');
const messages = new Counter('ws_messages_total');

export const options = {
  vus: 10000,
  duration: '15m',
  thresholds: {
    ws_connect_success: ['rate>0.99'],
    ws_error_rate: ['rate<0.001'],
    ws_message_latency: ['p(99)<100'],
  },
};

function randomSymbol() {
  const syms = ['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD','USDCHF','NZDUSD'];
  return syms[Math.floor(Math.random() * syms.length)];
}

export default function () {
  const token = `${__ENV.WS_TOKEN_PREFIX || ''}${__VU}`;
  const url = `${__ENV.WS_URL}?token=${token}`;
  const start = Date.now();
  const res = ws.connect(url, {}, function (socket) {
    socket.on('open', function () {
      connectSuccess.add(true);
      for (let i = 0; i < 3; i++) {
        socket.send(JSON.stringify({ event: 'subscribe', topic: `market_data:${randomSymbol()}` }));
      }
    });
    socket.on('message', function () {
      messages.add(1);
      latency.add(Date.now() - start);
    });
    socket.on('error', function () {
      errorRate.add(true);
    });
    socket.setTimeout(function () {
      socket.close();
    }, 900000);
  });
  check(res, { 'ws status 101': (r) => r && r.status === 101 });
  sleep(1);
}
