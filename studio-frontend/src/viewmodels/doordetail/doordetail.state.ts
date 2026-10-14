import type { DoorResponse, ValidationReportResponse } from '@/models';

export interface DoorDetailState {
    selectedDoor: string | null;
    door: DoorResponse | null;
    loading: boolean;
    error: string | null;
    editing: boolean;
    draft: string;
    saving: boolean;
    saveError: string | null;
    lastReport: ValidationReportResponse | null;
}
