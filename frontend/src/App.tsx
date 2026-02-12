import { Navigate, Route, Routes } from 'react-router-dom';
import MT5ConnectionManager from './components/MT5ConnectionManager';
import EconomicCalendar from './components/EconomicCalendar';
import ActivePositionsTable from './components/ActivePositionsTable';
import StrategyPerformanceDashboard from './components/StrategyPerformanceDashboard';
import ModelRegistryUI from './components/ModelRegistryUI';
import BacktestRunner from './components/BacktestRunner';
import { useAuth } from './contexts/AuthContext';
import { useState } from 'react';

function AuthScreen() {
  const { login, register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  return <div className='min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 to-amber-950 text-slate-100'><div className='bg-slate-900 p-6 rounded-xl w-[420px] space-y-2'><input className='w-full p-2 rounded bg-slate-800' placeholder='Email' value={email} onChange={(e)=>setEmail(e.target.value)}/><input className='w-full p-2 rounded bg-slate-800' placeholder='Password' type='password' value={password} onChange={(e)=>setPassword(e.target.value)}/><input className='w-full p-2 rounded bg-slate-800' placeholder='2FA Code (optional)' value={code} onChange={(e)=>setCode(e.target.value)}/><div className='flex gap-2'><button className='px-4 py-2 rounded bg-emerald-700' onClick={()=>login(email,password,code)}>Login</button><button className='px-4 py-2 rounded bg-blue-700' onClick={()=>register(email,password)}>Register</button></div></div></div>;
}

function Dashboard() {
  const { logout } = useAuth();
  return <div className='min-h-screen bg-slate-950 text-slate-100 p-4 space-y-4'><div className='flex justify-between items-center'><h1 className='text-2xl font-bold'>MTrader</h1><button onClick={logout} className='px-3 py-2 rounded bg-rose-700'>Logout</button></div><MT5ConnectionManager/><EconomicCalendar/><ActivePositionsTable/><StrategyPerformanceDashboard/><ModelRegistryUI/><BacktestRunner/></div>;
}

export default function App() {
  const { isAuthenticated } = useAuth();
  return <Routes><Route path='/' element={isAuthenticated ? <Dashboard/> : <AuthScreen/>}/><Route path='*' element={<Navigate to='/'/>}/></Routes>;
}
