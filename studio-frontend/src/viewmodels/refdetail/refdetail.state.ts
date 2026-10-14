import type { RefDetailResponse, ValidationReportResponse } from '@/models';

export interface RefDetailState {
    ref: RefDetailResponse | null;
    loading: boolean;
    error: string | null;
    editingSection: number | null;
    editingDoc: boolean;
    draft: string;
    saving: boolean;
    saveError: string | null;
    lastReport: ValidationReportResponse | null;
}
