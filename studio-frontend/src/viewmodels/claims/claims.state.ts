import type { IntentClaimResponse, ValidationReportResponse } from '@/models';

export interface ClaimsState {
    claims: IntentClaimResponse[];
    loading: boolean;
    error: string | null;
    validating: boolean;
    report: ValidationReportResponse | null;
}
