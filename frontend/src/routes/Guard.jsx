import { Navigate, Outlet } from 'react-router-dom';
import { useStore } from '../store';

export const landing = () => '/dashboard';

export default function Guard({ roles }) {
  const me = useStore((state) => state.me);

  if (!me) {
    return <Navigate to="/login" replace />;
  }

  if (roles && !roles.includes(me.role)) {
    return <Navigate to={landing(me.role)} replace />;
  }

  return <Outlet />;
}
