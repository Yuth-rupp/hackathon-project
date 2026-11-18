'use client';

import React from 'react';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { Footer } from './Footer';
import { DataFreshness } from '@/components/common/DataFreshness';
import { Radio } from 'lucide-react';

interface DashboardLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  lastUpdated?: string | Date;
}

export function DashboardLayout({
  children,
  title,
  subtitle,
  actions,
  lastUpdated,
}: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col antialiased">
      {/* Top Navbar */}
      <Navbar />

      {/* Main Workspace Frame */}
      <div className="flex flex-1 overflow-hidden">
        {/* Collapsible Left Sidebar */}
        <Sidebar />

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
          {/* Header section if provided */}
          {(title || actions) && (
            <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-navy-800/80 pb-5">
              <div>
                {title && (
                  <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                    {title}
                  </h1>
                )}
                {subtitle && (
                  <p className="mt-1 text-sm text-slate-400">
                    {subtitle}
                  </p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <DataFreshness timestamp={lastUpdated} />
                {actions}
              </div>
            </div>
          )}

          {/* Child Page Content */}
          <div className="space-y-6">
            {children}
          </div>
        </main>
      </div>

      {/* Global Footer */}
      <Footer />
    </div>
  );
}
