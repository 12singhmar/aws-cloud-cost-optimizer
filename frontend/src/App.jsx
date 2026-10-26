import React, { useState, useEffect, useCallback } from 'react';
import { dashboardData as fallbackMockData } from './data/mockData';
import { fetchHealth, fetchScenarios, fetchDashboard, fetchChangePassport } from './services/api';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import SummaryCards from './components/SummaryCards';
import CostTrend from './components/CostTrend';
import ServiceSpend from './components/ServiceSpend';
import PriorityFindings from './components/PriorityFindings';
import RecentActivity from './components/RecentActivity';
import RecommendationDrawer from './components/RecommendationDrawer';
import ChangePassportModal from './components/ChangePassportModal';
import FutureSectionNotice from './components/FutureSectionNotice';
import './App.css';

/**
 * AWS Cloud Cost Optimiser - Main Application
 * 
 * Cost Optimisation Command Center Dashboard.
 * Analyses cloud spend, highlights prioritised opportunities with explainable evidence,
 * cross-functional Change Passports, What-If simulation, and complete dark/light theme support.
 */
function App() {
  // Theme state: dark | light, with localStorage persistence & system preference fallback
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('theme');
      if (saved === 'dark' || saved === 'light') return saved;
      return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch {
      return 'light';
    }
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('theme', theme);
    } catch {
      // Fallback if storage blocked
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  // Backend health status tracking
  const [backendStatus, setBackendStatus] = useState('checking');

  // Scenarios state
  const [scenarios, setScenarios] = useState([
    { id: 'high-cost-waste', name: 'High Cost & Resource Waste' },
    { id: 'healthy-environment', name: 'Healthy Cloud Environment' },
    { id: 'mixed-environment', name: 'Mixed Environment' },
    { id: 'insufficient-data', name: 'Insufficient Data' },
  ]);
  const [selectedScenario, setSelectedScenario] = useState('high-cost-waste');

  // Dashboard data and network states
  const [dashboard, setDashboard] = useState(fallbackMockData);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // UI navigation & drawer states
  const [activeNav, setActiveNav] = useState('overview');
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [futureSectionName, setFutureSectionName] = useState(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Change Passport modal states
  const [passportModalOpen, setPassportModalOpen] = useState(false);
  const [passportData, setPassportData] = useState(null);

  // Load scenarios list and initial scenario data
  const loadScenarioData = useCallback(async (scenarioId) => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const data = await fetchDashboard(scenarioId);
      setDashboard(data);
      setSelectedScenario(scenarioId);
      setBackendStatus('ok');
    } catch (err) {
      console.warn('Dashboard fetch failed:', err.message);
      setBackendStatus('error');
      setErrorMessage(`Failed to load scenario '${scenarioId}': ${err.message}. Showing previous active data.`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial mount: check health, load scenarios list, load default scenario
  useEffect(() => {
    let isMounted = true;

    async function init() {
      try {
        await fetchHealth();
        if (isMounted) setBackendStatus('ok');

        const availableScenarios = await fetchScenarios();
        if (isMounted && availableScenarios?.length > 0) {
          setScenarios(availableScenarios);
        }

        if (isMounted) {
          await loadScenarioData(selectedScenario);
        }
      } catch (err) {
        if (isMounted) {
          console.warn('Backend unavailable on mount:', err.message);
          setBackendStatus('error');
        }
      }
    }

    init();

    return () => {
      isMounted = false;
    };
  }, [loadScenarioData, selectedScenario]);

  // Handle scenario switch from header
  const handleSelectScenario = (newScenarioId) => {
    if (newScenarioId === selectedScenario && !errorMessage) return;
    setSelectedFinding(null); // Close any open finding drawer
    setPassportModalOpen(false); // Close passport modal if open
    loadScenarioData(newScenarioId);
  };

  // Handle opening the Change Passport for a finding
  const handleOpenPassport = async (finding) => {
    if (!finding) return;
    try {
      const passport = await fetchChangePassport(finding.id, selectedScenario);
      setPassportData(passport);
      setPassportModalOpen(true);
    } catch (err) {
      console.error('Failed to load Change Passport:', err);
    }
  };

  // Handle sidebar navigation selection
  const handleSelectNav = (navId, isAvailable) => {
    if (isAvailable) {
      setActiveNav(navId);
      setFutureSectionName(null);
    } else {
      const labels = {
        recommendations: 'Full Recommendations Catalogue',
        resources: 'AWS Resources Inventory',
        activity: 'Historical Activity Logs',
        settings: 'Platform Settings & Thresholds',
      };
      setFutureSectionName(labels[navId] || 'This section');
    }
  };

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <Sidebar
        activeNav={activeNav}
        onSelectNav={handleSelectNav}
        isOpen={isMobileMenuOpen}
        onClose={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="main-wrapper">
        {/* Top Header with Scenario Selector, Simulation Badge, & Theme Toggle */}
        <Header
          month={dashboard.metadata.month}
          statusText={dashboard.metadata.statusText}
          backendStatus={backendStatus}
          scenarios={scenarios}
          selectedScenario={selectedScenario}
          onSelectScenario={handleSelectScenario}
          isLoading={isLoading}
          onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          theme={theme}
          onToggleTheme={toggleTheme}
        />

        {/* Dashboard Command Center */}
        <main className="dashboard-content">
          {/* Error Banner with Retry (if any) */}
          {errorMessage && (
            <div className="dashboard-notice-banner error-banner" role="alert">
              <div className="notice-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <div className="notice-body">
                <span className="notice-text">{errorMessage}</span>
              </div>
              <button
                type="button"
                className="notice-retry-btn"
                onClick={() => loadScenarioData(selectedScenario)}
              >
                Retry
              </button>
            </div>
          )}

          {/* Data Limitations Notice (for Insufficient Data scenario) */}
          {dashboard.metadata.dataLimitationsActive && (
            <div className="dashboard-notice-banner limitation-banner" role="status">
              <div className="notice-icon limitation-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </div>
              <div className="notice-body">
                <h4 className="notice-title">Observability Gaps & Data Limitations Active</h4>
                <p className="notice-text">
                  {dashboard.metadata.dataLimitationsNotice || 
                    "Sufficient observation windows or CloudWatch metrics are unavailable for some resources. Preconditions require verified data before generating recommendations."}
                </p>
              </div>
            </div>
          )}

          {/* Executive Summary KPI Cards */}
          <SummaryCards summary={dashboard.summary} />

          {/* Primary Dashboard Grid */}
          <div className={`dashboard-grid ${isLoading ? 'dashboard-grid-loading' : ''}`}>
            {/* Left Column: Priority Findings & Service Spend */}
            <div className="grid-column">
              {/* Priority Findings - Core Value of Product */}
              <PriorityFindings
                findings={dashboard.priorityFindings}
                onSelectFinding={(finding) => setSelectedFinding(finding)}
                selectedFindingId={selectedFinding?.id}
              />

              {/* Service Spend Breakdown */}
              <ServiceSpend serviceSpend={dashboard.serviceSpend} />
            </div>

            {/* Right Column: Cost Trend & Recent Activity */}
            <div className="grid-column">
              {/* 6-Month Cost Trend Chart */}
              <CostTrend costTrend={dashboard.costTrend} />

              {/* Recent Scan & Analysis Activity */}
              <RecentActivity
                activities={dashboard.recentActivity}
                lastAnalysis={dashboard.metadata.lastAnalysis}
                statusText={dashboard.metadata.statusText}
              />
            </div>
          </div>
        </main>
      </div>

      {/* Slide-out Recommendation Detail Drawer */}
      <RecommendationDrawer
        finding={selectedFinding}
        isOpen={Boolean(selectedFinding)}
        onClose={() => setSelectedFinding(null)}
        onOpenPassport={handleOpenPassport}
      />

      {/* Change Passport Workspace Modal */}
      {passportModalOpen && passportData && (
        <ChangePassportModal
          key={passportData.passport_id}
          passport={passportData}
          isOpen={passportModalOpen}
          onClose={() => setPassportModalOpen(false)}
          scenarioId={selectedScenario}
          onSimulationUpdated={() => loadScenarioData(selectedScenario)}
        />
      )}

      {/* Future Section Notice Toast */}
      <FutureSectionNotice
        sectionName={futureSectionName}
        onClose={() => setFutureSectionName(null)}
      />
    </div>
  );
}

export default App;
