import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Button, ErrorAlert, Field, Input } from "@/components/ui";
import { setSessionExpired, useSessionExpired } from "@/lib/session";
import { formatLeft, useTimeLeft } from "@/lib/timeLeft";
import type { Me } from "@/lib/types";

import { useDemoLogin, useExtendSession, useLogin, useLoginMfa, useLogout } from "./api";

/** Warn this long before a session ends. */
const WARN_MS = 2 * 60_000;

/**
 * Session timeout: a warning shortly before the sign-in ends ("Stay signed in"; demo accounts
 * are told their copy will be discarded), then a popup that keeps the page open and asks for
 * the password again — or, for the demo, offers a fresh demo.
 */
export function SessionWatch({ me }: { me: Me | null | undefined }) {
  const expired = useSessionExpired();
  // The popup still needs who was signed in after `me` turns null.
  const [last, setLast] = useState<Me | null>(null);
  if (me && me !== last) setLast(me);
  const user = me ?? last;
  const left = useTimeLeft(user?.session_expires_at);

  useEffect(() => {
    if (left !== null && left <= 0 && me) setSessionExpired(true);
  }, [left, me]);

  if (!user) return null;
  if (expired) return <ExpiredDialog user={user} />;
  if (left !== null && left <= WARN_MS) return <Warning user={user} left={left} />;
  return null;
}

function Warning({ user, left }: { user: Me; left: number }) {
  const { t } = useTranslation();
  const extend = useExtendSession();
  return (
    <div
      role="status"
      className="border-bark-100 bg-surface fixed inset-x-4 bottom-4 z-50 mx-auto flex max-w-xl flex-wrap items-center gap-3 rounded-lg border p-3 text-sm shadow-lg"
    >
      <span className="flex-1">
        {user.is_sandbox
          ? t("session.demoEndsIn", { time: formatLeft(left) })
          : t("session.endsIn", { time: formatLeft(left) })}
      </span>
      <ErrorAlert error={extend.error} />
      {!user.is_sandbox && (
        <Button busy={extend.isPending} onClick={() => extend.mutate()}>
          {t("session.staySignedIn")}
        </Button>
      )}
    </div>
  );
}

function ExpiredDialog({ user }: { user: Me }) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-expired-title"
        className="bg-surface w-full max-w-sm space-y-4 rounded-lg p-5 shadow-xl"
      >
        <h2 id="session-expired-title" className="text-lg font-semibold">
          {user.is_sandbox ? t("session.demoEndedTitle") : t("session.expiredTitle")}
        </h2>
        {user.is_sandbox ? <DemoEnded /> : <SignInAgain user={user} />}
      </div>
    </div>
  );
}

function SignInAgain({ user }: { user: Me }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const login = useLogin();
  const mfa = useLoginMfa();
  const logout = useLogout();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"password" | "mfa">("password");

  const done = () => {
    setSessionExpired(false);
    void qc.invalidateQueries();
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (step === "mfa") {
      mfa.mutate(code.trim(), { onSuccess: done });
      return;
    }
    login.mutate(
      { email: user.email, password },
      {
        onSuccess: (data) => {
          if (data.status === "mfa_required") setStep("mfa");
          else done();
        },
      },
    );
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <p className="text-bark-700 text-sm">{t("session.expiredHint", { email: user.email })}</p>
      <ErrorAlert error={step === "mfa" ? mfa.error : login.error} />
      {step === "password" ? (
        <Field label={t("auth.password")}>
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="current-password"
              autoFocus
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
      ) : (
        <Field label={t("auth.code")}>
          {(id) => (
            <Input
              id={id}
              autoComplete="one-time-code"
              autoFocus
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          )}
        </Field>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          variant="ghost"
          onClick={() =>
            logout.mutate(undefined, {
              onSettled: () => {
                setSessionExpired(false);
                void navigate("/login", { replace: true });
              },
            })
          }
        >
          {t("auth.signOut")}
        </Button>
        <Button type="submit" busy={login.isPending || mfa.isPending}>
          {t("session.refresh")}
        </Button>
      </div>
    </form>
  );
}

function DemoEnded() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const demo = useDemoLogin();
  return (
    <div className="space-y-4">
      <p className="text-bark-700 text-sm">{t("session.demoEndedHint")}</p>
      <ErrorAlert error={demo.error} />
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          variant="ghost"
          onClick={() => {
            setSessionExpired(false);
            void navigate("/login", { replace: true });
          }}
        >
          {t("auth.signIn")}
        </Button>
        <Button
          busy={demo.isPending}
          onClick={() =>
            demo.mutate(undefined, {
              onSuccess: () => {
                setSessionExpired(false);
                void navigate("/", { replace: true });
              },
            })
          }
        >
          {t("session.newDemo")}
        </Button>
      </div>
    </div>
  );
}

/** "Demo · 23:41 left" in the header for demo accounts. */
export function DemoBadge({ me }: { me: Me }) {
  const { t } = useTranslation();
  const left = useTimeLeft(me.session_expires_at);
  if (!me.is_sandbox) return null;
  return (
    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
      {left !== null ? t("session.demoBadge", { time: formatLeft(left) }) : t("trees.demo")}
    </span>
  );
}
