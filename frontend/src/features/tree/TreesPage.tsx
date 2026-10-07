import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import {
  Badge,
  Button,
  Card,
  Dialog,
  ErrorAlert,
  Field,
  Input,
  PageHeader,
  Spinner,
  TextArea,
} from "@/components/ui";
import { useMe } from "@/features/auth/api";

import { useCreateTree, useTrees } from "./api";

export function TreesPage() {
  const { t } = useTranslation();
  const me = useMe();
  const trees = useTrees();
  const [creating, setCreating] = useState(false);

  return (
    <div>
      <PageHeader
        title={t("trees.title")}
        actions={
          me.data?.is_superadmin && (
            <Button onClick={() => setCreating(true)}>{t("trees.create")}</Button>
          )
        }
      />
      {trees.isPending && <Spinner />}
      <ErrorAlert error={trees.error} />
      {trees.data?.length === 0 && (
        <Card>
          <p className="text-bark-700">
            {me.data?.is_superadmin ? t("trees.emptyAdmin") : t("trees.empty")}
          </p>
        </Card>
      )}
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {trees.data?.map((tree) => (
          <li key={tree.id}>
            <Link
              to={`/trees/${tree.id}`}
              className="border-bark-100 hover:border-leaf-600 bg-surface block h-full rounded-lg border p-4 shadow-sm transition"
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <h2 className="font-serif text-lg font-semibold">{tree.name}</h2>
                <span className="flex shrink-0 gap-1">
                  {tree.is_demo && <Badge tone="amber">{t("trees.demo")}</Badge>}
                  <Badge>{t(`roles.${tree.my_role}`)}</Badge>
                </span>
              </div>
              {tree.description && (
                <p className="text-bark-700 line-clamp-3 text-sm">{tree.description}</p>
              )}
            </Link>
          </li>
        ))}
      </ul>
      <CreateTreeDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function CreateTreeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const create = useCreateTree();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      { name, description: description || null },
      {
        onSuccess: () => {
          setName("");
          setDescription("");
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open={open} onClose={onClose} title={t("trees.create")}>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label={t("trees.name")}>
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
        <Field label={t("trees.description")}>
          {(id) => (
            <TextArea
              id={id}
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </Field>
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
