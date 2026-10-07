import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  Badge,
  Button,
  Checkbox,
  CopyField,
  Dialog,
  ErrorAlert,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";
import { useMe } from "@/features/auth/api";
import { SUPPORTED_LANGUAGES } from "@/i18n";
import type { Language, LinkResponse, User } from "@/lib/types";

import {
  useAdminDisable2fa,
  useCreateUser,
  useDeleteUser,
  useResetLink,
  useUpdateUser,
  useUsers,
} from "./api";

export function UsersPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"" | "true" | "false">("");
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const users = useUsers({
    q: q || undefined,
    is_active: status === "" ? undefined : status === "true",
    offset,
  });

  return (
    <div>
      <PageHeader
        title={t("users.title")}
        actions={<Button onClick={() => setCreating(true)}>{t("users.create")}</Button>}
      />
      <div className="mb-4 flex flex-wrap gap-3">
        <Input
          type="search"
          className="max-w-xs"
          placeholder={t("users.search")}
          aria-label={t("users.search")}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
        />
        <Select
          className="max-w-48"
          aria-label={t("users.status")}
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as "" | "true" | "false");
            setOffset(0);
          }}
        >
          <option value="">{t("users.all")}</option>
          <option value="true">{t("users.active")}</option>
          <option value="false">{t("users.inactive")}</option>
        </Select>
      </div>
      {users.isPending && <Spinner />}
      <ErrorAlert error={users.error} />
      {users.data && (
        <>
          <div className="border-bark-100 overflow-x-auto rounded-lg border bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-bark-100 bg-bark-50 text-bark-700 border-b">
                <tr>
                  <th className="px-3 py-2">{t("users.name")}</th>
                  <th className="px-3 py-2">{t("users.status")}</th>
                  <th className="px-3 py-2">{t("users.lastLogin")}</th>
                  <th className="px-3 py-2 text-right">{t("users.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-bark-100 divide-y">
                {users.data.items.map((u) => (
                  <UserRow key={u.id} user={u} />
                ))}
              </tbody>
            </table>
          </div>
          <Pager total={users.data.total} offset={offset} limit={50} onChange={setOffset} />
        </>
      )}
      <CreateUserDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

export function Pager({
  total,
  offset,
  limit,
  onChange,
}: {
  total: number;
  offset: number;
  limit: number;
  onChange: (offset: number) => void;
}) {
  const { t } = useTranslation();
  if (total <= limit) return null;
  return (
    <div className="text-bark-700 mt-3 flex items-center justify-between text-sm">
      <span>
        {t("common.range", { from: offset + 1, to: Math.min(offset + limit, total), total })}
      </span>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          {t("common.previous")}
        </Button>
        <Button
          variant="secondary"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          {t("common.next")}
        </Button>
      </div>
    </div>
  );
}

function UserRow({ user }: { user: User }) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const me = useMe();
  const update = useUpdateUser();
  const del = useDeleteUser();
  const resetLink = useResetLink();
  const disable2fa = useAdminDisable2fa();
  const [link, setLink] = useState<LinkResponse | null>(null);
  const isSelf = me.data?.id === user.id;
  const error = update.error ?? del.error ?? resetLink.error ?? disable2fa.error;

  return (
    <tr className="align-top">
      <td className="px-3 py-2">
        <div className="font-medium">
          {user.display_name}{" "}
          {user.is_superadmin && <Badge tone="amber">{t("users.superadmin")}</Badge>}
        </div>
        <div className="text-bark-700">{user.email}</div>
        {error && (
          <div className="mt-2">
            <ErrorAlert error={error} />
          </div>
        )}
      </td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap gap-1">
          <Badge tone={user.is_active ? "green" : "red"}>
            {user.is_active ? t("users.active") : t("users.inactive")}
          </Badge>
          {user.totp_enabled && <Badge>2FA</Badge>}
        </div>
      </td>
      <td className="text-bark-700 px-3 py-2">{formatDate(user.last_login_at)}</td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap justify-end gap-1">
          <Button
            variant="ghost"
            busy={resetLink.isPending}
            onClick={() => resetLink.mutate(user.id, { onSuccess: setLink })}
          >
            {t("users.resetLink")}
          </Button>
          {user.totp_enabled && (
            <Button
              variant="ghost"
              onClick={() => {
                if (window.confirm(t("users.confirmDisable2fa", { name: user.display_name })))
                  disable2fa.mutate(user.id);
              }}
            >
              {t("users.disable2fa")}
            </Button>
          )}
          {!isSelf && (
            <>
              <Button
                variant="ghost"
                onClick={() => update.mutate({ id: user.id, is_superadmin: !user.is_superadmin })}
              >
                {user.is_superadmin ? t("users.revokeSuperadmin") : t("users.makeSuperadmin")}
              </Button>
              <Button
                variant="ghost"
                onClick={() => update.mutate({ id: user.id, is_active: !user.is_active })}
              >
                {user.is_active ? t("users.deactivate") : t("users.activate")}
              </Button>
              <Button
                variant="ghost"
                className="text-red-700"
                onClick={() => {
                  if (window.confirm(t("users.confirmDelete", { name: user.display_name })))
                    del.mutate(user.id);
                }}
              >
                {t("common.delete")}
              </Button>
            </>
          )}
        </div>
        <Dialog open={link !== null} onClose={() => setLink(null)} title={t("users.resetLink")}>
          {link && (
            <div className="space-y-3">
              <p className="text-bark-700 text-sm">
                {t("users.resetLinkHint", {
                  name: user.display_name,
                  date: formatDate(link.expires_at),
                })}
              </p>
              <CopyField value={link.url} />
            </div>
          )}
        </Dialog>
      </td>
    </tr>
  );
}

function CreateUserDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const create = useCreateUser();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [language, setLanguage] = useState<Language>("uk");
  const [superadmin, setSuperadmin] = useState(false);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        email,
        display_name: name,
        password,
        preferred_language: language,
        is_superadmin: superadmin,
      },
      {
        onSuccess: () => {
          setEmail("");
          setName("");
          setPassword("");
          setSuperadmin(false);
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open={open} onClose={onClose} title={t("users.create")}>
      <form onSubmit={onSubmit} className="space-y-4">
        <p className="text-bark-700 text-sm">{t("users.createHint")}</p>
        <Field label={t("auth.email")}>
          {(id) => (
            <Input
              id={id}
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
        </Field>
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
        <Field label={t("auth.password")} hint={t("auth.passwordRules")}>
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="new-password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
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
        <Checkbox
          label={t("users.superadmin")}
          checked={superadmin}
          onChange={(e) => setSuperadmin(e.target.checked)}
        />
        <ErrorAlert error={create.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" busy={create.isPending}>
            {t("common.create")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
