import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { Logo } from "@/components/Logo";
import { Button, Card, ErrorAlert, Field, Input } from "@/components/ui";
import { safeNext } from "@/lib/nav";

import { useLogin, useLoginMfa, useMe } from "./api";

export function LoginPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const me = useMe();
  const login = useLogin();
  const mfa = useLoginMfa();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"password" | "mfa">("password");
  const next = safeNext(params.get("next"));

  if (me.data) return <Navigate to={next} replace />;

  const onPassword = (e: FormEvent) => {
    e.preventDefault();
    login.mutate(
      { email, password },
      {
        onSuccess: (data) => {
          if (data.status === "mfa_required") setStep("mfa");
          else void navigate(next, { replace: true });
        },
      },
    );
  };

  const onMfa = (e: FormEvent) => {
    e.preventDefault();
    mfa.mutate(code.trim(), { onSuccess: () => void navigate(next, { replace: true }) });
  };

  return (
    <div className="mx-auto max-w-sm py-8">
      <Logo className="mx-auto mb-2 size-20" />
      <h1 className="text-leaf-700 mb-1 text-center font-serif text-3xl font-semibold">
        {t("app.name")}
      </h1>
      <p className="text-bark-700 mb-6 text-center text-sm">{t("app.tagline")}</p>
      <Card>
        {step === "password" ? (
          <form onSubmit={onPassword} className="space-y-4">
            <h2 className="font-semibold">{t("auth.signIn")}</h2>
            <ErrorAlert error={login.error} />
            <Field label={t("auth.email")}>
              {(id) => (
                <Input
                  id={id}
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              )}
            </Field>
            <Field label={t("auth.password")}>
              {(id) => (
                <Input
                  id={id}
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              )}
            </Field>
            <Button type="submit" className="w-full" busy={login.isPending}>
              {t("auth.signIn")}
            </Button>
            <p className="text-bark-700 text-xs">{t("auth.forgotHint")}</p>
          </form>
        ) : (
          <form onSubmit={onMfa} className="space-y-4">
            <h2 className="font-semibold">{t("auth.mfaTitle")}</h2>
            <p className="text-bark-700 text-sm">{t("auth.mfaHint")}</p>
            <ErrorAlert error={mfa.error} />
            <Field label={t("auth.code")}>
              {(id) => (
                <Input
                  id={id}
                  inputMode="text"
                  autoComplete="one-time-code"
                  autoFocus
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              )}
            </Field>
            <Button type="submit" className="w-full" busy={mfa.isPending}>
              {t("auth.verify")}
            </Button>
            <Button
              variant="ghost"
              className="w-full"
              onClick={() => {
                setStep("password");
                setCode("");
              }}
            >
              {t("common.back")}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
