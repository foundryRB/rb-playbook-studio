export type StudioView =
    | 'map'
    | 'map3d'
    | 'playbook'
    | 'galaxy'
    | 'nebula'
    | 'ref'
    | 'skill'
    | 'agent'
    | 'door'
    | 'create'
    | 'createskill'
    | 'createagent'
    | 'createdoor';

export interface NavState {
    view: StudioView;
    /** Which sidebar sections are open, keyed `galaxy:<name>` / `ref:<id>`.
     *  Absent means collapsed: the tree opens closed and reveals on demand. */
    expanded: Record<string, boolean>;
}
