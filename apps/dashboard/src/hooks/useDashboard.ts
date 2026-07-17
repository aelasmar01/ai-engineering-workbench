import { QueryClient, useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { fetchDashboardState, runTaskAction } from "../api/client";

export const queryClient = new QueryClient();

export function useDashboard() {
  const [view, setView] = useState<View>("today");
  const [selectedTaskId, setSelectedTaskId] = useState<string>("");
  const stateQuery = useQuery({
    queryKey: ["dashboard-state"],
    queryFn: fetchDashboardState,
    refetchInterval: 10_000
  });
  const state = stateQuery.data;
  const selectedTask = useMemo(() => {
    if (!state) {
      return null;
    }
    return state.tasks.find((task) => task.id === selectedTaskId) ?? state.tasks[0] ?? null;
  }, [selectedTaskId, state]);
  const actionMutation = useMutation({
    mutationFn: runTaskAction,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["dashboard-state"] });
    }
  });

  return {
    actionMutation,
    selectedTask,
    setSelectedTaskId,
    setView,
    state,
    stateQuery,
    view
  };
}

export type View = "today" | "projects" | "task" | "sessions" | "validation" | "review" | "metrics";

export const views: Array<{ id: View; label: string }> = [
  { id: "today", label: "Today" },
  { id: "projects", label: "Projects" },
  { id: "task", label: "Task Detail" },
  { id: "sessions", label: "Sessions" },
  { id: "validation", label: "Validation" },
  { id: "review", label: "Review" },
  { id: "metrics", label: "Metrics" }
];
