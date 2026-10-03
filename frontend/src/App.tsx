import { Navigate, Route, Routes } from 'react-router-dom';
import { NeutralLandingPage } from './pages/public/NeutralLandingPage';
import { RegistrationPage } from './pages/public/RegistrationPage';
import { ManagePage } from './pages/public/ManagePage';
import { ResultsPage } from './pages/public/ResultsPage';
import { TimingCapturePage } from './pages/public/TimingCapturePage';
import { TeamLoginPage } from './pages/team/TeamLoginPage';
import { TeamLayout } from './pages/team/TeamLayout';
import { TeamIndexRedirect } from './pages/team/TeamIndexRedirect';
import { RoleGate } from './pages/team/RoleGate';
import { ReceptionPage } from './pages/team/ReceptionPage';
import { CertificatePrintPage } from './pages/team/CertificatePrintPage';
import { RaceOperationsPage } from './pages/team/RaceOperationsPage';
import { SponsorsPage } from './pages/team/SponsorsPage';
import { EventAdminPage } from './pages/team/EventAdminPage';
import { StatsPage } from './pages/team/StatsPage';
import { SepaExportPage } from './pages/team/SepaExportPage';
import { PlatformAdminPage } from './pages/platform/PlatformAdminPage';
import { NotFoundPage } from './pages/NotFoundPage';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<NeutralLandingPage />} />
      <Route path="/platform" element={<PlatformAdminPage />} />
      <Route path="/:slug/teilnahme" element={<RegistrationPage />} />
      <Route path="/:slug/manage" element={<ManagePage />} />
      <Route path="/:slug/ergebnisse" element={<ResultsPage />} />
      <Route path="/:slug/timing" element={<TimingCapturePage mode="kiosk" />} />
      <Route path="/:slug/team/login" element={<TeamLoginPage />} />
      <Route path="/:slug/team" element={<TeamLayout />}>
        <Route index element={<TeamIndexRedirect />} />
        <Route
          path="admin"
          element={
            <RoleGate roles={['race_office']}>
              <ReceptionPage />
            </RoleGate>
          }
        />
        <Route
          path="ergebnisdruck"
          element={
            <RoleGate roles={['race_office']}>
              <CertificatePrintPage />
            </RoleGate>
          }
        />
        <Route
          path="zeiterfassung"
          element={
            <RoleGate roles={['timing', 'race_office']}>
              <TimingCapturePage mode="team" />
            </RoleGate>
          }
        />
        <Route
          path="special-admin"
          element={
            <RoleGate roles={['race_office']}>
              <RaceOperationsPage />
            </RoleGate>
          }
        />
        <Route
          path="sponsoren"
          element={
            <RoleGate roles={['sponsor_management']}>
              <SponsorsPage />
            </RoleGate>
          }
        />
        <Route
          path="events"
          element={
            <RoleGate roles={['race_office']}>
              <EventAdminPage />
            </RoleGate>
          }
        />
        <Route
          path="statistiken"
          element={
            <RoleGate roles={['viewer', 'race_office']}>
              <StatsPage />
            </RoleGate>
          }
        />
        <Route
          path="sepa"
          element={
            <RoleGate roles={['sepa']}>
              <SepaExportPage />
            </RoleGate>
          }
        />
        <Route path="*" element={<Navigate to="." replace />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
