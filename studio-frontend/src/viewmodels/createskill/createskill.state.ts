import type { ValidationReportResponse } from '@/models';

export interface CreateSkillState {
    name: string;
    description: string;
    refs: string[];
    galaxy: string;
    /** Emails, as typed; split when the form is sent. */
    owners: string;
    submitting: boolean;
    error: string | null;
    report: ValidationReportResponse | null;
}
