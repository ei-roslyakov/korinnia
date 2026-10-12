import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";

import { Layout } from "@/components/Layout";
import { AdminLayout } from "@/features/admin/AdminLayout";
import { PersonEditorPage } from "@/features/builder/PersonEditorPage";
import { TrashPage } from "@/features/builder/TrashPage";
import { ImportPage } from "@/features/imports/ImportPage";
import { AuditLogPage } from "@/features/admin/AuditLogPage";
import { InvitationsPage } from "@/features/admin/InvitationsPage";
import { SystemPage } from "@/features/admin/SystemPage";
import { AdminTreesPage } from "@/features/admin/AdminTreesPage";
import { UsersPage } from "@/features/admin/UsersPage";
import { AcceptInvitePage } from "@/features/auth/AcceptInvitePage";
import { OpenSharedLinkPage } from "@/features/share/OpenSharedLinkPage";
import { HelpPage } from "@/features/help/HelpPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProfilePage } from "@/features/auth/ProfilePage";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { ModerationPage } from "@/features/collab/ModerationPage";
import { QualityPage } from "@/features/collab/QualityPage";
import { OnThisDayPage } from "@/features/insights/OnThisDayPage";
import { RelationshipPage } from "@/features/insights/RelationshipPage";
import { StatsPage } from "@/features/insights/StatsPage";
import { TimelinePage } from "@/features/insights/TimelinePage";
import { PersonPage } from "@/features/person/PersonPage";
import { SourcesPage } from "@/features/sources/SourcesPage";
import { StoriesPage } from "@/features/stories/StoriesPage";
import { StoryEditorPage } from "@/features/stories/StoryEditorPage";
import { StoryPage } from "@/features/stories/StoryPage";
import { MembersPage } from "@/features/tree/MembersPage";
import { TreeViewPage } from "@/features/tree/TreeViewPage";
import { TreesPage } from "@/features/tree/TreesPage";
import { Spinner } from "@/components/ui";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ToastProvider } from "@/components/Toast";

// Leaflet and the map page load only when the map is opened.
const MapPage = lazy(() => import("@/features/map/MapPage"));

export function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<Layout />}>
          {/* Public */}
          <Route path="login" element={<LoginPage />} />
          <Route path="invite/:token" element={<AcceptInvitePage />} />
          <Route path="s/:token" element={<OpenSharedLinkPage />} />
          <Route path="help" element={<HelpPage />} />
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
            path="trees/:treeId/sources"
            element={
              <RequireAuth>
                <SourcesPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/stories"
            element={
              <RequireAuth>
                <StoriesPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/stories/new"
            element={
              <RequireAuth>
                <StoryEditorPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/stories/:storyId"
            element={
              <RequireAuth>
                <StoryPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/stories/:storyId/edit"
            element={
              <RequireAuth>
                <StoryEditorPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/moderation"
            element={
              <RequireAuth>
                <ModerationPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/quality"
            element={
              <RequireAuth>
                <QualityPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/timeline"
            element={
              <RequireAuth>
                <TimelinePage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/map"
            element={
              <RequireAuth>
                <Suspense fallback={<Spinner />}>
                  <MapPage />
                </Suspense>
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/on-this-day"
            element={
              <RequireAuth>
                <OnThisDayPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/relationship"
            element={
              <RequireAuth>
                <RelationshipPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/stats"
            element={
              <RequireAuth>
                <StatsPage />
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
            path="trees/:treeId/import"
            element={
              <RequireAuth>
                <ImportPage />
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
            <Route path="trees" element={<AdminTreesPage />} />
            <Route path="invitations" element={<InvitationsPage />} />
            <Route path="audit" element={<AuditLogPage />} />
            <Route path="system" element={<SystemPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ToastProvider>
  );
}
