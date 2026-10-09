import { Navigate, Route, Routes } from 'react-router-dom';
import { useStore } from './store';
import Guard, { landing } from './routes/Guard';
import AppLayout from './layouts/AppLayout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Alerts from './pages/Alerts';
import AlertEventDetails from './pages/AlertEventDetails';
import Admin from './pages/Admin';

export default function App() {
  const me = useStore((state) => state.me);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/alerts/event/:eventId" element={<AlertEventDetails />} />
          <Route element={<Guard roles={['ADMIN']} />}>
            <Route path="/admin" element={<Admin />} />
          </Route>
        </Route>
      </Route>
      <Route
        path="*"
        element={<Navigate to={me ? landing(me.role) : '/login'} replace />}
      />
    </Routes>
  );
}
