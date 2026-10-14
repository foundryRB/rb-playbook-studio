import type { ValidationReportResponse } from '@/models';

export interface CreateAgentState {
    name: string;
    title: string;
    description: string;
    refs: string[];
    skills: string[];
    doors: string[];
    galaxy: string;
    /** Emails, as typed; split when the form is sent. */
    owners: string;
    writes: boolean;
    freshEyes: boolean;
    submitting: boolean;
    error: string | null;
    report: ValidationReportResponse | null;
}
