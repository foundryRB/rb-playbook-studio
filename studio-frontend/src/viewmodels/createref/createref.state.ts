import type { ValidationReportResponse } from '@/models';

export interface CreateRefState {
    name: string;
    domain: string;
    galaxy: string;
    title: string;
    summary: string;
    submitting: boolean;
    error: string | null;
    report: ValidationReportResponse | null;
}
