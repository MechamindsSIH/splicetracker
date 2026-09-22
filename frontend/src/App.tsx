import { Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import Architecture3D from './pages/Architecture3D';
import LiveInspection from './pages/LiveInspection';
import SpliceDetail from './pages/SpliceDetail';
import ConditionHistory from './pages/ConditionHistory';
import TemporalTwin from './pages/TemporalTwin';
import Alerts from './pages/Alerts';
import Analytics from './pages/Analytics';
import Hardware from './pages/Hardware';
import Simulation from './pages/Simulation';
import Settings from './pages/Settings';
import PipelineView from './pages/PipelineView';
import EventInspector from './pages/EventInspector';
import MaintenanceCenter from './pages/MaintenanceCenter';

export default function App() {
  return (
    <MainLayout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/architecture" element={<Architecture3D />} />
        <Route path="/inspection" element={<LiveInspection />} />
        <Route path="/splice/:id" element={<SpliceDetail />} />
        <Route path="/history" element={<ConditionHistory />} />
        <Route path="/twin" element={<TemporalTwin />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/hardware" element={<Hardware />} />
        <Route path="/simulation" element={<Simulation />} />
        <Route path="/maintenance" element={<MaintenanceCenter />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/pipeline" element={<PipelineView />} />
        <Route path="/events/:id" element={<EventInspector />} />
      </Routes>
    </MainLayout>
  );
}
