import { useEffect, useState } from 'react';
import { TradingAPI } from '../services/api';

export default function MT5ConnectionManager() {
  const [form, setForm] = useState({ account_id: '', password: '', server: '' });
  const [accounts, setAccounts] = useState<any[]>([]);
  const [status, setStatus] = useState('disconnected');

  const load = async () => setAccounts((await TradingAPI.getAccounts()).data || []);
  useEffect(() => { load(); }, []);

  const test = async () => {
    const { data } = await TradingAPI.testMT5(form);
    setStatus(data.ok ? 'test-ok' : 'test-failed');
  };

  const connect = async () => {
    const { data } = await TradingAPI.connectMT5(form);
    setStatus(data.connected ? 'connected' : 'failed');
    await load();
  };

  return (
    <div className='rounded-xl p-4 bg-slate-900 text-slate-100'>
      <h2 className='text-lg font-semibold mb-2'>MT5 Connection Manager</h2>
      <div className='grid grid-cols-3 gap-2'>
        <input className='p-2 rounded bg-slate-800' placeholder='Account ID' value={form.account_id} onChange={(e)=>setForm({...form,account_id:e.target.value})} />
        <input className='p-2 rounded bg-slate-800' placeholder='Password' type='password' value={form.password} onChange={(e)=>setForm({...form,password:e.target.value})} />
        <input className='p-2 rounded bg-slate-800' placeholder='Server' value={form.server} onChange={(e)=>setForm({...form,server:e.target.value})} />
      </div>
      <div className='mt-2 flex gap-2'>
        <button onClick={test} className='px-3 py-2 rounded bg-emerald-700'>Test</button>
        <button onClick={connect} className='px-3 py-2 rounded bg-blue-700'>Connect</button>
      </div>
      <p className='mt-2'>Status: <span className='font-mono'>{status}</span></p>
      <ul className='mt-2 space-y-1'>
        {accounts.map((a)=> <li key={a.id} className='flex justify-between bg-slate-800 p-2 rounded'><span>{a.account_login}@{a.server}</span><button className='text-sky-300' onClick={()=>TradingAPI.switchAccount(a.id)}>Switch</button></li>)}
      </ul>
    </div>
  );
}
