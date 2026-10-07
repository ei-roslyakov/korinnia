import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useMatch, useNavigate } from "react-router";

import { useLogout, useMe } from "@/features/auth/api";
import { hadStoredLanguage } from "@/i18n";
import { getMeta } from "@/lib/api";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { Logo } from "./Logo";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { versionLabel } from "@/lib/version";

const FIRST_YEAR = 2026;
const THIS_YEAR = new Date().getFullYear();
const COPYRIGHT_YEARS = THIS_YEAR > FIRST_YEAR ? `${FIRST_YEAR}–${THIS_YEAR}` : `${FIRST_YEAR}`;

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

  // Visitors who never chose a language get the installation default (DEFAULT_LANGUAGE).
  const meta = useQuery({
    queryKey: ["meta"],
    queryFn: getMeta,
    staleTime: Infinity,
    retry: false,
  });
  const installDefault = meta.data?.default_language;
  useEffect(() => {
    if (preferred || hadStoredLanguage || !installDefault) return;
    if (installDefault !== i18n.resolvedLanguage) void i18n.changeLanguage(installDefault);
  }, [installDefault, preferred, i18n]);

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm ${isActive ? "font-semibold text-leaf-700" : "text-bark-700 hover:text-bark-900"}`;

  return (
    <div className={fullBleed ? "flex h-dvh flex-col" : "flex min-h-full flex-col"}>
      <header className="border-bark-100 bg-surface border-b">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 print:hidden">
          <div className="flex items-center gap-6">
            <Link
              to="/"
              className="text-leaf-700 flex items-center gap-2 font-serif text-xl font-semibold"
            >
              <Logo className="size-9 shrink-0" />
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
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <ThemeSwitcher />
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
      {!fullBleed && (
        <footer className="border-bark-100 text-bark-700 border-t print:hidden">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs">
            <span>
              © {COPYRIGHT_YEARS} Yevhenii Rosliakov · {t("app.name")} · {t("footer.rights")}
            </span>
            <span className="flex items-center gap-3">
              <span title={t("footer.version")} className="tabular-nums">
                {versionLabel()}
              </span>
              <a href="/third-party-notices.txt" className="hover:text-bark-900 underline">
                {t("footer.thirdParty")}
              </a>
            </span>
          </div>
        </footer>
      )}
    </div>
  );
}
