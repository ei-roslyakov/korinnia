import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";

export function AdminLayout() {
  const { t } = useTranslation();
  const tab = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-leaf-700 text-on-leaf" : "text-bark-700 hover:bg-bark-100"}`;
  return (
    <div>
      <nav className="mb-6 flex flex-wrap gap-2" aria-label={t("nav.admin")}>
        <NavLink to="/admin/users" className={tab}>
          {t("users.title")}
        </NavLink>
        <NavLink to="/admin/invitations" className={tab}>
          {t("invitations.title")}
        </NavLink>
        <NavLink to="/admin/audit" className={tab}>
          {t("audit.title")}
        </NavLink>
        <NavLink to="/admin/system" className={tab}>
          {t("status.title")}
        </NavLink>
      </nav>
      <Outlet />
    </div>
  );
}
