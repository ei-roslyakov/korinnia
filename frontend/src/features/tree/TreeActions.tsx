import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Button, Dialog, ErrorAlert, Field, Input } from "@/components/ui";
import { useErrorMessage } from "@/lib/hooks";
import type { Tree } from "@/lib/types";

import { useDeleteTree, useUpdateTree } from "./api";

/**
 * Rename and Delete for a tree's admins (on the tree list and in builder mode). Deleting is
 * a soft delete; `leaveTo` is where to go afterwards when the tree itself is open.
 */
export function TreeActions({
  tree,
  leaveTo,
  className = "",
  buttonClassName = "",
}: {
  tree: Pick<Tree, "id" | "name" | "my_role">;
  leaveTo?: string;
  className?: string;
  buttonClassName?: string;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const del = useDeleteTree(tree.id);
  const errorMessage = useErrorMessage();
  const [renaming, setRenaming] = useState(false);
  if (tree.my_role !== "admin") return null;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {del.error && (
        <span role="alert" className="truncate text-xs text-red-700">
          {errorMessage(del.error)}
        </span>
      )}
      <Button
        variant="ghost"
        className={buttonClassName}
        aria-label={t("trees.renameNamed", { name: tree.name })}
        onClick={() => setRenaming(true)}
      >
        {t("trees.rename")}
      </Button>
      <Button
        variant="ghost"
        className={`text-red-700 ${buttonClassName}`}
        aria-label={t("trees.deleteNamed", { name: tree.name })}
        busy={del.isPending}
        onClick={() => {
          if (!window.confirm(t("trees.confirmDelete", { name: tree.name }))) return;
          del.mutate(undefined, {
            onSuccess: () => {
              if (leaveTo) void navigate(leaveTo, { replace: true });
            },
          });
        }}
      >
        {t("common.delete")}
      </Button>
      {renaming && <RenameTreeDialog tree={tree} onClose={() => setRenaming(false)} />}
    </div>
  );
}

function RenameTreeDialog({
  tree,
  onClose,
}: {
  tree: Pick<Tree, "id" | "name">;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const update = useUpdateTree(tree.id);
  const [name, setName] = useState(tree.name);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    update.mutate({ name }, { onSuccess: onClose });
  };

  return (
    <Dialog open onClose={onClose} title={t("trees.rename")}>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label={t("trees.name")}>
          {(id) => (
            <Input
              id={id}
              required
              autoFocus
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
        </Field>
        <ErrorAlert error={update.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" busy={update.isPending} disabled={!name.trim()}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
