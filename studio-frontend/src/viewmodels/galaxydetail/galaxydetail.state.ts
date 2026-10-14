import type { GalaxyResponse } from '@/models';

export interface GalaxyDetailState {
    selectedGalaxy: string | null;
    galaxyDoc: GalaxyResponse | null;
    loading: boolean;
    error: string | null;
}
