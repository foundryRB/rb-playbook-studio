import type { SkillResponse, ValidationReportResponse } from '@/models';

export interface SkillDetailState {
    selectedSkill: string | null;
    skill: SkillResponse | null;
    loading: boolean;
    error: string | null;
    activeFile: string;
    fileContent: string | null;
    fileLoading: boolean;
    editing: boolean;
    draft: string;
    saving: boolean;
    saveError: string | null;
    installing: boolean;
    lastReport: ValidationReportResponse | null;
}
