import { Navigate, Route, Routes } from "react-router";

import { Layout } from "@/components/Layout";
import { AdminLayout } from "@/features/admin/AdminLayout";
import { PersonEditorPage } from "@/features/builder/PersonEditorPage";
import { TrashPage } from "@/features/builder/TrashPage";
import { AuditLogPage } from "@/features/admin/AuditLogPage";
import { InvitationsPage } from "@/features/admin/InvitationsPage";
import { SystemPage } from "@/features/admin/SystemPage";
import { UsersPage } from "@/features/admin/UsersPage";
import { AcceptInvitePage } from "@/features/auth/AcceptInvitePage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProfilePage } from "@/features/auth/ProfilePage";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { PersonPage } from "@/features/person/PersonPage";
import { MembersPage } from "@/features/tree/MembersPage";
import { TreeViewPage } from "@/features/tree/TreeViewPage";
import { TreesPage } from "@/features/tree/TreesPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Public */}
        <Route path="login" element={<LoginPage />} />
        <Route path="invite/:token" element={<AcceptInvitePage />} />
        <Route path="reset-password/:token" element={<ResetPasswordPage />} />

        {/* Signed-in users */}
        <Route
          index
          element={
            <RequireAuth>
              <TreesPage />
            </RequireAuth>
          }
        />
        <Route
          path="profile"
          element={
            <RequireAuth>
              <ProfilePage />
            </RequireAuth>
          }
        />
        <Route
          path="trees/:treeId"
          element={
            <RequireAuth>
              <TreeViewPage />
            </RequireAuth>
          }
        />
        <Route
          path="trees/:treeId/people/:personId"
          element={
            <RequireAuth>
              <PersonPage />
            </RequireAuth>
          }
        />
        <Route
          path="trees/:treeId/people/:personId/edit"
          element={
            <RequireAuth>
              <PersonEditorPage />
            </RequireAuth>
          }
        />
        <Route
          path="trees/:treeId/trash"
          element={
            <RequireAuth>
              <TrashPage />
            </RequireAuth>
          }
        />
        <Route
          path="trees/:treeId/members"
          element={
            <RequireAuth>
              <MembersPage />
            </RequireAuth>
          }
        />
        <Route
          path="trees/:treeId/audit"
          element={
            <RequireAuth>
              <AuditLogPage />
            </RequireAuth>
          }
        />

        {/* Superadmin */}
        <Route
          path="admin"
          element={
            <RequireAuth superadmin>
              <AdminLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="users" replace />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="invitations" element={<InvitationsPage />} />
          <Route path="audit" element={<AuditLogPage />} />
          <Route path="system" element={<SystemPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
