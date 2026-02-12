import { useEffect, useMemo, useState } from 'react';
import { TradingAPI } from '../services/api';

export default function EconomicCalendar() {
  const [events, setEvents] = useState<any[]>([]);
  const [country, setCountry] = useState('');
  const [impact, setImpact] = useState('');

  const load = async () => {
    const { data } = await TradingAPI.getCalendar({ country, impact });
    setEvents(data || []);
  };
  useEffect(() => { load(); }, [country, impact]);

  const next = useMemo(()=>events.find((e)=>new Date(e.time).getTime() > Date.now()), [events]);
  const countdown = next ? Math.max(0, Math.floor((new Date(next.time).getTime()-Date.now())/1000)) : 0;

  return (
    <div className='rounded-xl p-4 bg-slate-900 text-slate-100'>
      <h2 className='text-lg font-semibold'>Economic Calendar</h2>
      <div className='flex gap-2 my-2'>
        <input className='p-2 rounded bg-slate-800' placeholder='Country' value={country} onChange={(e)=>setCountry(e.target.value)} />
        <select className='p-2 rounded bg-slate-800' value={impact} onChange={(e)=>setImpact(e.target.value)}>
          <option value=''>All impact</option><option value='low'>Low</option><option value='medium'>Medium</option><option value='high'>High</option>
        </select>
      </div>
      <p className='text-sm mb-2'>Next event countdown: {countdown}s</p>
      <table className='w-full text-sm'>
        <thead><tr><th>Time</th><th>Event</th><th>Impact</th><th>Bias</th><th>Actual/Forecast</th></tr></thead>
        <tbody>{events.map((e)=> <tr key={e.id}><td>{new Date(e.time).toLocaleString()}</td><td>{e.event_name}</td><td>{e.impact}</td><td>{e.bias_prediction} ({Math.round((e.confidence||0)*100)}%)</td><td>{e.actual}/{e.forecast}</td></tr>)}</tbody>
      </table>
    </div>
  );
}
