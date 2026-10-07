import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { Spinner } from "@/components/ui";

import { useMe } from "./api";

/** Renders children only for a logged-in user (optionally a superadmin); else redirects. */
export function RequireAuth({
  children,
  superadmin = false,
}: {
  children: ReactNode;
  superadmin?: boolean;
}) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }
  if (!me.data) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (superadmin && !me.data.is_superadmin) return <Navigate to="/" replace />;
  return <>{children}</>;
}
