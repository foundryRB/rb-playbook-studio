import type { NebulaDetailResponse, NebulaSummaryResponse } from '@/models';

export interface NebulaeState {
    /** null until the first load settles; [] when the corpus has no nebulae. */
    nebulae: NebulaSummaryResponse[] | null;
    loading: boolean;
    error: string | null;
    selectedNebula: string | null;
    detail: NebulaDetailResponse | null;
    detailLoading: boolean;
    detailError: string | null;
}
