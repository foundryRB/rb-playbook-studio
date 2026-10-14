import type { GraphResponse } from '@/models';

export interface GraphState {
    graph: GraphResponse | null;
    loading: boolean;
    error: string | null;
    selectedRef: string | null;
    hoveredNode: string | null;
    /** null means every domain is visible; otherwise the focus set. */
    visibleDomains: string[] | null;
    showSkills: boolean;
    showAgents: boolean;
    showDoors: boolean;
    /** null means the universe view; a name scopes the map to that galaxy. */
    galaxy: string | null;
}
