"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Dashboard } from "../components/dashboard";
import { loadDashboardBootstrap } from "../lib/api-client";
import type { DashboardBootstrap } from "../lib/api-types";

const loadingData: DashboardBootstrap = {
  scenarios: { status: "loading" }, forecasts: { status: "loading" }, exploration: { status: "loading" },
  operational: { status: "loading" }, experiments: { status: "loading" },
};

export default function HomePage() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  const [data, setData] = useState<DashboardBootstrap>(loadingData);
  const [loading, setLoading] = useState(true);
  const requestVersion = useRef(0);

  const refresh = useCallback(() => {
    const version = ++requestVersion.current;
    setLoading(true);
    void loadDashboardBootstrap(apiBaseUrl).then((response) => {
      if (version === requestVersion.current) {
        setData(response);
        setLoading(false);
      }
    });
  }, [apiBaseUrl]);

  useEffect(() => { refresh(); }, [refresh]);

  return <Dashboard apiBaseUrl={apiBaseUrl} data={data} loading={loading} onRefresh={refresh} />;
}
