import type { AgentResponse, ValidationReportResponse } from '@/models';

export interface AgentDetailState {
    selectedAgent: string | null;
    agent: AgentResponse | null;
    loading: boolean;
    error: string | null;
    editing: boolean;
    draft: string;
    saving: boolean;
    saveError: string | null;
    lastReport: ValidationReportResponse | null;
}
