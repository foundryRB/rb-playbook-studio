import type { ValidationReportResponse } from '@/models';

export type CardKind = 'mcp' | 'rag';

export interface CreateDoorState {
    kind: CardKind;
    name: string;
    galaxy: string;
    /** The whole card: frontmatter and doctrine. */
    raw: string;
    /** Emails, as typed; split when the form is sent. */
    owners: string;
    submitting: boolean;
    error: string | null;
    report: ValidationReportResponse | null;
}
