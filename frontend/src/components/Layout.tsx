import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useMatch, useNavigate } from "react-router";

import { useLogout, useMe } from "@/features/auth/api";

import { LanguageSwitcher } from "./LanguageSwitcher";

export function Layout() {
  const { t, i18n } = useTranslation();
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const preferred = me.data?.preferred_language;
  // The tree canvas uses the full viewport below the header.
  const fullBleed = useMatch("/trees/:treeId") !== null;

  // Apply the user's saved language once their profile is known.
  useEffect(() => {
    if (preferred && preferred !== i18n.resolvedLanguage) void i18n.changeLanguage(preferred);
  }, [preferred, i18n]);

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm ${isActive ? "font-semibold text-leaf-700" : "text-bark-700 hover:text-bark-900"}`;

  return (
    <div className={fullBleed ? "flex h-dvh flex-col" : "flex min-h-full flex-col"}>
      <header className="border-bark-100 border-b bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 print:hidden">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-leaf-700 font-serif text-xl font-semibold">
              {t("app.name")}
            </Link>
            {me.data && (
              <nav className="flex gap-4" aria-label={t("nav.main")}>
                <NavLink to="/" end className={navClass}>
                  {t("nav.trees")}
                </NavLink>
                {me.data.is_superadmin && (
                  <NavLink to="/admin" className={navClass}>
                    {t("nav.admin")}
                  </NavLink>
                )}
              </nav>
            )}
          </div>
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            {me.data && (
              <>
                <NavLink to="/profile" className={navClass}>
                  {me.data.display_name}
                </NavLink>
                <button
                  type="button"
                  className="text-bark-700 hover:text-bark-900 text-sm"
                  onClick={() =>
                    logout.mutate(undefined, {
                      onSettled: () => void navigate("/login", { replace: true }),
                    })
                  }
                >
                  {t("auth.signOut")}
                </button>
              </>
            )}
          </div>
        </div>
      </header>
      <main
        className={
          fullBleed ? "flex min-h-0 flex-1 flex-col" : "mx-auto w-full max-w-6xl flex-1 px-4 py-8"
        }
      >
        <Outlet />
      </main>
    </div>
  );
}
