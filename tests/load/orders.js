import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const submitLatency = new Trend('order_submit_latency_ms');
const fillRate = new Rate('order_fill_rate');
const dbWriteLatency = new Trend('db_write_latency_ms');

export const options = {
  scenarios: {
    high_throughput: {
      executor: 'constant-arrival-rate',
      rate: 1000,
      timeUnit: '1s',
      duration: '10m',
      preAllocatedVUs: 200,
      maxVUs: 2000,
    },
  },
  thresholds: {
    order_submit_latency_ms: ['p(95)<500'],
    order_fill_rate: ['rate>0.9'],
  },
};

function randomOrder() {
  const symbols = ['EURUSD','GBPUSD','USDJPY','AUDUSD'];
  const types = ['MARKET','LIMIT','STOP'];
  return {
    client_order_id: `${__VU}-${Date.now()}-${Math.random()}`,
    symbol: symbols[Math.floor(Math.random()*symbols.length)],
    side: Math.random()>0.5?'BUY':'SELL',
    order_type: types[Math.floor(Math.random()*types.length)],
    quantity: 0.01 + Math.random()*0.2,
    price: 1 + Math.random(),
  };
}

export default function () {
  const payload = JSON.stringify(randomOrder());
  const t0 = Date.now();
  const res = http.post(`${__ENV.API_URL}/api/v1/orders`, payload, { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${__ENV.API_TOKEN}` } });
  submitLatency.add(Date.now() - t0);
  check(res, { 'status 200/201': (r) => r.status === 200 || r.status === 201 });
  if (res.status === 200 || res.status === 201) {
    const body = res.json();
    fillRate.add(body.status === 'FILLED' || body.status === 'SUBMITTED');
    if (body.db_write_ms) dbWriteLatency.add(body.db_write_ms);
  }
}
