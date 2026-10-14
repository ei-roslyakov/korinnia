import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  Alert,
  Badge,
  Button,
  Card,
  ErrorAlert,
  Field,
  Input,
  PageHeader,
  Select,
} from "@/components/ui";
import { SUPPORTED_LANGUAGES } from "@/i18n";
import type { Language, Me } from "@/lib/types";

import {
  useChangePassword,
  useMe,
  useRegenerateRecoveryCodes,
  useTotpDisable,
  useTotpEnable,
  useTotpSetup,
  useUpdateMe,
} from "./api";

export function ProfilePage() {
  const { t } = useTranslation();
  const me = useMe();
  if (!me.data) return null;
  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title={t("profile.title")} />
      <ProfileForm me={me.data} />
      {!me.data.is_sandbox && (
        <>
          <PasswordForm />
          <TwoFactorSection me={me.data} />
        </>
      )}
    </div>
  );
}

function ProfileForm({ me }: { me: Me }) {
  const { t, i18n } = useTranslation();
  const update = useUpdateMe();
  const [name, setName] = useState(me.display_name);
  const [language, setLanguage] = useState<Language>(me.preferred_language);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    update.mutate(
      { display_name: name, preferred_language: language },
      { onSuccess: () => void i18n.changeLanguage(language) },
    );
  };

  return (
    <Card>
      <form onSubmit={onSubmit} className="space-y-4">
        <h2 className="font-semibold">{t("profile.details")}</h2>
        <Field label={t("auth.email")}>{(id) => <Input id={id} value={me.email} disabled />}</Field>
        <Field label={t("profile.displayName")}>
          {(id) => (
            <Input
              id={id}
              required
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("profile.language")}>
          {(id) => (
            <Select
              id={id}
              value={language}
              onChange={(e) => setLanguage(e.target.value as Language)}
            >
              {SUPPORTED_LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <ErrorAlert error={update.error} />
        {update.isSuccess && <Alert kind="success">{t("common.saved")}</Alert>}
        <Button type="submit" busy={update.isPending}>
          {t("common.save")}
        </Button>
      </form>
    </Card>
  );
}

function PasswordForm() {
  const { t } = useTranslation();
  const change = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const mismatch = repeat.length > 0 && next !== repeat;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (mismatch) return;
    change.mutate(
      { current_password: current, new_password: next },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
          setRepeat("");
        },
      },
    );
  };

  return (
    <Card>
      <form onSubmit={onSubmit} className="space-y-4">
        <h2 className="font-semibold">{t("profile.changePassword")}</h2>
        <p className="text-bark-700 text-sm">{t("profile.changePasswordHint")}</p>
        <Field label={t("profile.currentPassword")}>
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("auth.newPassword")} hint={t("auth.passwordRules")}>
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="new-password"
              required
              minLength={10}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("auth.repeatPassword")}>
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="new-password"
              required
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
            />
          )}
        </Field>
        {mismatch && <Alert>{t("auth.passwordsDiffer")}</Alert>}
        <ErrorAlert error={change.error} />
        {change.isSuccess && <Alert kind="success">{t("profile.passwordChanged")}</Alert>}
        <Button type="submit" busy={change.isPending} disabled={mismatch}>
          {t("profile.changePassword")}
        </Button>
      </form>
    </Card>
  );
}

function RecoveryCodes({ codes }: { codes: string[] }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2">
      <Alert kind="info">{t("twoFactor.saveCodes")}</Alert>
      <ul className="bg-bark-50 grid grid-cols-2 gap-1 rounded-md p-3 font-mono text-sm">
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </div>
  );
}

function TwoFactorSection({ me }: { me: Me }) {
  const { t } = useTranslation();
  const setup = useTotpSetup();
  const enable = useTotpEnable();
  const disable = useTotpDisable();
  const regenerate = useRegenerateRecoveryCodes();
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const codes = enable.data?.recovery_codes ?? regenerate.data?.recovery_codes;

  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="font-semibold">{t("twoFactor.title")}</h2>
        <Badge tone={me.totp_enabled ? "green" : "neutral"}>
          {me.totp_enabled ? t("twoFactor.on") : t("twoFactor.off")}
        </Badge>
      </div>
      <p className="text-bark-700 mb-4 text-sm">{t("twoFactor.description")}</p>

      {codes && <RecoveryCodes codes={codes} />}

      {!me.totp_enabled && !setup.data && (
        <Button onClick={() => setup.mutate()} busy={setup.isPending}>
          {t("twoFactor.setUp")}
        </Button>
      )}

      {!me.totp_enabled && setup.data && (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            enable.mutate(code.trim(), { onSuccess: () => setCode("") });
          }}
        >
          <p className="text-sm">{t("twoFactor.scan")}</p>
          <img
            alt="QR"
            className="border-bark-100 size-48 rounded border"
            src={`data:image/svg+xml;utf8,${encodeURIComponent(setup.data.qr_svg)}`}
          />
          <p className="text-bark-700 text-xs">
            {t("twoFactor.manual")} <code className="font-mono">{setup.data.secret}</code>
          </p>
          <Field label={t("auth.code")}>
            {(id) => (
              <Input
                id={id}
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            )}
          </Field>
          <ErrorAlert error={enable.error} />
          <Button type="submit" busy={enable.isPending}>
            {t("twoFactor.enable")}
          </Button>
        </form>
      )}

      {me.totp_enabled && (
        <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
          <Field label={t("auth.code")} hint={t("twoFactor.codeOrRecovery")}>
            {(id) => (
              <Input
                id={id}
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            )}
          </Field>
          <Field label={t("auth.password")} hint={t("twoFactor.passwordToDisable")}>
            {(id) => (
              <Input
                id={id}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          <ErrorAlert error={disable.error ?? regenerate.error} />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={!code}
              busy={regenerate.isPending}
              onClick={() => regenerate.mutate(code.trim(), { onSuccess: () => setCode("") })}
            >
              {t("twoFactor.newCodes")}
            </Button>
            <Button
              variant="danger"
              disabled={!code || !password}
              busy={disable.isPending}
              onClick={() =>
                disable.mutate(
                  { password, code: code.trim() },
                  {
                    onSuccess: () => {
                      setCode("");
                      setPassword("");
                      setup.reset();
                      enable.reset();
                    },
                  },
                )
              }
            >
              {t("twoFactor.disable")}
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
