import type { ReactNode } from "react";
import { Navigate, useLocation, useParams } from "react-router";

import { Spinner } from "@/components/ui";
import { useShareSession } from "@/features/share/api";

import { useMe } from "./api";

/** Renders children only for a logged-in user (optionally a superadmin); else redirects.
 * A tree's pages are also open to a visitor who opened a share link to that tree (D98). */
export function RequireAuth({
  children,
  superadmin = false,
}: {
  children: ReactNode;
  superadmin?: boolean;
}) {
  const me = useMe();
  const location = useLocation();
  const { treeId } = useParams();
  const anonymous = me.isSuccess && !me.data;
  const shared = useShareSession(anonymous && Boolean(treeId) && !superadmin);
  if (me.isPending || (anonymous && shared.isLoading)) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }
  if (!me.data) {
    if (!superadmin && treeId && shared.data?.tree_id === treeId) return <>{children}</>;
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (superadmin && !me.data.is_superadmin) return <Navigate to="/" replace />;
  return <>{children}</>;
}
