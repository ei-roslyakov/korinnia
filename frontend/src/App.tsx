import { lazy, type ComponentType } from "react";
import { Navigate, Route, Routes } from "react-router";

import { Layout } from "@/components/Layout";
import { LoginPage } from "@/features/auth/LoginPage";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { TreesPage } from "@/features/tree/TreesPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ToastProvider } from "@/components/Toast";

// Pages load on first visit (route-level code splitting): the first load carries only the
// shell, sign-in and the tree list; the canvas (React Flow), Leaflet, the editors and the
// admin pages come as separate files.
function page<K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) {
  return lazy(() => load().then((m) => ({ default: m[name] })));
}

const AlbumPage = page(() => import("@/features/album/AlbumPage"), "AlbumPage");
const AdminLayout = page(() => import("@/features/admin/AdminLayout"), "AdminLayout");
const PersonEditorPage = page(
  () => import("@/features/builder/PersonEditorPage"),
  "PersonEditorPage",
);
const TrashPage = page(() => import("@/features/builder/TrashPage"), "TrashPage");
const ImportPage = page(() => import("@/features/imports/ImportPage"), "ImportPage");
const AuditLogPage = page(() => import("@/features/admin/AuditLogPage"), "AuditLogPage");
const InvitationsPage = page(() => import("@/features/admin/InvitationsPage"), "InvitationsPage");
const SystemPage = page(() => import("@/features/admin/SystemPage"), "SystemPage");
const AdminTreesPage = page(() => import("@/features/admin/AdminTreesPage"), "AdminTreesPage");
const UsersPage = page(() => import("@/features/admin/UsersPage"), "UsersPage");
const AcceptInvitePage = page(() => import("@/features/auth/AcceptInvitePage"), "AcceptInvitePage");
const OpenSharedLinkPage = page(
  () => import("@/features/share/OpenSharedLinkPage"),
  "OpenSharedLinkPage",
);
const HelpPage = page(() => import("@/features/help/HelpPage"), "HelpPage");
const ProfilePage = page(() => import("@/features/auth/ProfilePage"), "ProfilePage");
const ResetPasswordPage = page(
  () => import("@/features/auth/ResetPasswordPage"),
  "ResetPasswordPage",
);
const ModerationPage = page(() => import("@/features/collab/ModerationPage"), "ModerationPage");
const QualityPage = page(() => import("@/features/collab/QualityPage"), "QualityPage");
const OnThisDayPage = page(() => import("@/features/insights/OnThisDayPage"), "OnThisDayPage");
const RelationshipPage = page(
  () => import("@/features/insights/RelationshipPage"),
  "RelationshipPage",
);
const StatsPage = page(() => import("@/features/insights/StatsPage"), "StatsPage");
const TimelinePage = page(() => import("@/features/insights/TimelinePage"), "TimelinePage");
const PersonPage = page(() => import("@/features/person/PersonPage"), "PersonPage");
const SourcesPage = page(() => import("@/features/sources/SourcesPage"), "SourcesPage");
const StoriesPage = page(() => import("@/features/stories/StoriesPage"), "StoriesPage");
const StoryEditorPage = page(() => import("@/features/stories/StoryEditorPage"), "StoryEditorPage");
const StoryPage = page(() => import("@/features/stories/StoryPage"), "StoryPage");
const MembersPage = page(() => import("@/features/tree/MembersPage"), "MembersPage");
const TreeViewPage = page(() => import("@/features/tree/TreeViewPage"), "TreeViewPage");
const MapPage = lazy(() => import("@/features/map/MapPage"));
const PlacesPage = page(() => import("@/features/places/PlacesPage"), "PlacesPage");
const PlacePage = page(() => import("@/features/places/PlacePage"), "PlacePage");

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
            path="trees/:treeId/album"
            element={
              <RequireAuth>
                <AlbumPage />
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
                <MapPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/places"
            element={
              <RequireAuth>
                <PlacesPage />
              </RequireAuth>
            }
          />
          <Route
            path="trees/:treeId/places/:placeId"
            element={
              <RequireAuth>
                <PlacePage />
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
