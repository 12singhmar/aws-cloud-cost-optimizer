import React, { useState, useEffect } from 'react';
import { dashboardData } from './data/mockData';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import SummaryCards from './components/SummaryCards';
import CostTrend from './components/CostTrend';
import ServiceSpend from './components/ServiceSpend';
import PriorityFindings from './components/PriorityFindings';
import RecentActivity from './components/RecentActivity';
import RecommendationDrawer from './components/RecommendationDrawer';
import FutureSectionNotice from './components/FutureSectionNotice';
import './App.css';

/**
 * AWS Cloud Cost Optimiser - Main Application
 * 
 * Cost Optimisation Command Center Dashboard.
 * Analyses cloud spend, highlights prioritised opportunities with explainable evidence,
 * and maintains a read-only architecture without modifying AWS resources.
 */
function App() {
  // Backend health status tracking (preserves http://127.0.0.1:8000/api/health check)
  const [backendStatus, setBackendStatus] = useState('checking');

  // UI state management
  const [activeNav, setActiveNav] = useState('overview');
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [futureSectionName, setFutureSectionName] = useState(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Poll / check backend health endpoint on mount
  useEffect(() => {
    let isMounted = true;

    fetch('http://127.0.0.1:8000/api/health')
      .then((response) => {
        if (!response.ok) throw new Error('Backend response error');
        return response.json();
      })
      .then((data) => {
        if (isMounted) {
          setBackendStatus(data.status || 'ok');
        }
      })
      .catch(() => {
        if (isMounted) {
          // Graceful fallback: dashboard remains functional with mock data
          setBackendStatus('error');
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

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
        {/* Top Header */}
        <Header
          month={dashboardData.metadata.month}
          statusText={dashboardData.metadata.statusText}
          backendStatus={backendStatus}
          onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        />

        {/* Dashboard Command Center */}
        <main className="dashboard-content">
          {/* Executive Summary KPI Cards */}
          <SummaryCards summary={dashboardData.summary} />

          {/* Primary Dashboard Grid */}
          <div className="dashboard-grid">
            {/* Left Column: Priority Findings & Service Spend */}
            <div className="grid-column">
              {/* Priority Findings - Core Value of Product */}
              <PriorityFindings
                findings={dashboardData.priorityFindings}
                onSelectFinding={(finding) => setSelectedFinding(finding)}
                selectedFindingId={selectedFinding?.id}
              />

              {/* Service Spend Breakdown */}
              <ServiceSpend serviceSpend={dashboardData.serviceSpend} />
            </div>

            {/* Right Column: Cost Trend & Recent Activity */}
            <div className="grid-column">
              {/* 6-Month Cost Trend Chart */}
              <CostTrend costTrend={dashboardData.costTrend} />

              {/* Recent Scan & Analysis Activity */}
              <RecentActivity
                activities={dashboardData.recentActivity}
                lastAnalysis={dashboardData.metadata.lastAnalysis}
                statusText={dashboardData.metadata.statusText}
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
      />

      {/* Future Section Notice Toast */}
      <FutureSectionNotice
        sectionName={futureSectionName}
        onClose={() => setFutureSectionName(null)}
      />
    </div>
  );
}

export default App;