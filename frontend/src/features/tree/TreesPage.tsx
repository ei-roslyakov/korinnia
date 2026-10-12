import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import {
  Badge,
  Button,
  Dialog,
  ErrorAlert,
  Field,
  Input,
  PageHeader,
  TextArea,
} from "@/components/ui";
import { EmptyState } from "@/components/EmptyState";
import { Logo } from "@/components/Logo";
import { CardsSkeleton } from "@/components/Skeleton";
import { useMe } from "@/features/auth/api";
import { NewTreeImport } from "@/features/imports/NewTreeImport";
import type { Tree } from "@/lib/types";

import { useCreateTree, useTrees } from "./api";
import { TreeActions } from "./TreeActions";

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
          me.data?.can_create_trees && (
            <>
              <NewTreeImport />
              <Button onClick={() => setCreating(true)}>{t("trees.create")}</Button>
            </>
          )
        }
      />
      {trees.isPending && <CardsSkeleton label={t("common.loading")} />}
      <ErrorAlert error={trees.error} />
      {trees.data?.length === 0 && (
        <EmptyState
          title={t("trees.emptyTitle")}
          hint={me.data?.can_create_trees ? t("trees.emptyAdmin") : t("trees.empty")}
          action={
            me.data?.can_create_trees && (
              <div className="flex flex-wrap justify-center gap-2">
                <Button onClick={() => setCreating(true)}>{t("trees.create")}</Button>
                <NewTreeImport />
              </div>
            )
          }
        />
      )}
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {trees.data?.map((tree) => (
          <TreeCard key={tree.id} tree={tree} />
        ))}
      </ul>
      <CreateTreeDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

/** A tree's card; its admins can rename or delete the tree from here. */
function TreeCard({ tree }: { tree: Tree }) {
  const { t } = useTranslation();
  const canManage = tree.my_role === "admin";

  return (
    <li className="relative">
      <Link
        to={`/trees/${tree.id}`}
        className={`border-bark-100 hover:border-leaf-600 bg-surface block h-full rounded-lg border p-4 shadow-sm transition ${canManage ? "pb-12" : ""}`}
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          {tree.cover?.length ? (
            <div className="flex -space-x-3" aria-hidden="true">
              {tree.cover.map((url) => (
                <img
                  key={url}
                  src={url}
                  alt=""
                  loading="lazy"
                  className="border-surface size-12 rounded-full border-2 object-cover shadow-sm"
                />
              ))}
            </div>
          ) : (
            <Logo className="size-12" />
          )}
          <span className="flex shrink-0 gap-1">
            {tree.is_demo && <Badge tone="amber">{t("trees.demo")}</Badge>}
            <Badge>{t(`roles.${tree.my_role}`)}</Badge>
          </span>
        </div>
        <h2 className="font-serif text-lg font-semibold">{tree.name}</h2>
        <p className="text-bark-700 mb-2 text-xs">
          {[
            t("trees.people", { count: tree.person_count ?? 0 }),
            tree.first_year && tree.last_year && `${tree.first_year} – ${tree.last_year}`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {tree.description && (
          <p className="text-bark-700 line-clamp-3 text-sm">{tree.description}</p>
        )}
      </Link>
      {/* Outside the link: a button cannot sit inside an <a>. */}
      <TreeActions
        tree={tree}
        className="absolute right-3 bottom-3 left-4 justify-end"
        buttonClassName="text-xs"
      />
    </li>
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
