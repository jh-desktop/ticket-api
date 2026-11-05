import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from './components/Layout'
import { AuditPage } from './pages/AuditPage'
import { DocsPage } from './pages/DocsPage'
import { GlossaryPage } from './pages/GlossaryPage'
import { LoginPage } from './pages/LoginPage'
import { RolesPage } from './pages/RolesPage'
import { SnapshotsPage } from './pages/SnapshotsPage'
import { StructurePage } from './pages/StructurePage'
import { TicketsPage } from './pages/TicketsPage'
import { AuthProvider } from './state/auth'
import { CallsProvider } from './state/calls'
import { GlossaryProvider } from './state/glossary'

export default function App() {
  return (
    <BrowserRouter>
      <CallsProvider>
        <AuthProvider>
          <GlossaryProvider>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<StructurePage />} />
                <Route path="login" element={<LoginPage />} />
                <Route path="tickets" element={<TicketsPage />} />
                <Route path="roles" element={<RolesPage />} />
                <Route path="audit" element={<AuditPage />} />
                <Route path="snapshots" element={<SnapshotsPage />} />
                <Route path="glossary" element={<GlossaryPage />} />
                <Route path="docs/:name?" element={<DocsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </GlossaryProvider>
        </AuthProvider>
      </CallsProvider>
    </BrowserRouter>
  )
}
