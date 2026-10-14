import type { PlaybookResponse, ValidationReportResponse } from '@/models';

export interface PlaybookState {
    doc: PlaybookResponse | null;
    loading: boolean;
    error: string | null;
    editing: boolean;
    draft: string;
    saving: boolean;
    saveError: string | null;
    lastReport: ValidationReportResponse | null;
}
