import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { VRButton } from 'three/addons/webxr/VRButton.js';

import {
    DEFAULT_CARTOGRAPHY_QUALITY,
    PlanetForge,
    archetypeOf,
    cartographyWidth,
    type PlanetAssets,
} from '@/three/planetCartography';
import {
    makeAnamorphicStreak,
    makeDetailNormal,
    makeNebulaTexture,
    makeParticleSprite,
    makePlanetMaterial,
    makePortalMaterial,
    makeRingTexture,
    makeSpikedCorona,
    makeSunMaterial,
    makeWindowStrip,
} from '@/three/proceduralTextures';
import { layoutDocument, type DocLine } from '@/viewmodels/graph/panel.model';
import {
    createPositionResolver,
    galaxyDiscRadius,
    hashSeed,
    seededRandom,
    type SceneBody,
    type UniverseModel,
    type Vec3,
} from '@/viewmodels/graph/scene.model';

/** The immersive universe per REF-ThreeJS: one SceneApp the host mounts and
 *  disposes, one setAnimationLoop shared by flat and XR rendering, seeded
 *  procedural detail (planet textures, coronas, galaxy particle discs), and
 *  documents readable on an in-scene panel. Bloom runs in flat mode; XR
 *  renders the same scene directly (comfort budget). */

export interface UniverseSceneStats {
    bodies: number;
    moons: number;
    galaxies: number;
    nebulae: number;
    xrEnabled: boolean;
    bloom: boolean;
    panelOpen: boolean;
    texturesPending: number;
}

export interface UniverseSnapshot {
    meanLuma: number;
    maxLuma: number;
    brightFraction: number;
    distinctHues: number;
}

interface PanelState {
    title: string;
    meta: string;
    lines: DocLine[];
    scroll: number;
    accent: string;
}

interface PanelLinkRect {
    x0: number;
    y0: number;
    x1: number;
    y1: number;
    target: string;
}

interface SunOffset {
    current: THREE.Vector3;
    from: THREE.Vector3;
    to: THREE.Vector3;
    start: number;
}

interface CameraTween {
    fromPosition: THREE.Vector3;
    toPosition: THREE.Vector3;
    fromTarget: THREE.Vector3;
    toTarget: THREE.Vector3;
    offset: THREE.Vector3;
    start: number;
    duration: number;
}

const HOME_POSITION = new THREE.Vector3(0, 3.6, 8.0);
const MOON_VARIANTS = 6;
const HOME_TARGET = new THREE.Vector3(0, 1.35, 0);
const PANEL_WIDTH = 1.15;
const PANEL_HEIGHT = 0.8;
const PANEL_CANVAS_W = 1150;
const PANEL_CANVAS_H = 800;

interface PanelLineSpec {
    font: string;
    fill: string;
    lineHeight: number;
}

const panelSpecs = (accent: string): Record<string, PanelLineSpec> => ({
    h1: { font: '800 30px system-ui, sans-serif', fill: '#f8fafc', lineHeight: 44 },
    h2: { font: '700 25px system-ui, sans-serif', fill: accent, lineHeight: 40 },
    h3: { font: '600 22px system-ui, sans-serif', fill: '#e2e8f0', lineHeight: 34 },
    body: { font: '20px system-ui, sans-serif', fill: '#cbd5e1', lineHeight: 27 },
    bullet: { font: '20px system-ui, sans-serif', fill: '#cbd5e1', lineHeight: 27 },
    quote: { font: 'italic 20px system-ui, sans-serif', fill: '#94a3b8', lineHeight: 27 },
    code: { font: '18px ui-monospace, monospace', fill: '#93c5fd', lineHeight: 25 },
    gap: { font: '20px system-ui, sans-serif', fill: '#cbd5e1', lineHeight: 14 },
});

export class UniverseSceneApp {
    private readonly container: HTMLElement;
    private readonly onSelect: (body: SceneBody) => void;
    private readonly model: UniverseModel;
    private readonly resolve: (id: string, t: number) => Vec3;
    private readonly renderer: THREE.WebGLRenderer;
    private readonly composer: EffectComposer;
    private readonly scene = new THREE.Scene();
    private readonly camera: THREE.PerspectiveCamera;
    private readonly controls: OrbitControls;
    private lastTime: number | null = null;
    private readonly raycaster = new THREE.Raycaster();
    private readonly pointer = new THREE.Vector2();
    private readonly resizeObserver: ResizeObserver;
    private readonly pickables: THREE.Object3D[] = [];
    private readonly byMesh = new Map<THREE.Object3D, SceneBody>();
    private readonly meshById = new Map<string, THREE.Mesh>();
    private readonly labels = new Map<THREE.Object3D, THREE.Sprite>();
    private readonly spins = new Map<THREE.Mesh, number>();
    /** Ships face where they are going; heading is read off the resolver each frame. */
    private readonly ships: { mesh: THREE.Mesh; id: string }[] = [];
    private readonly halos: { sprite: THREE.Sprite; base: number; seed: number }[] = [];
    private readonly sunMaterials: THREE.ShaderMaterial[] = [];
    private readonly portalMaterials: THREE.ShaderMaterial[] = [];
    private readonly planetShades: {
        material: THREE.ShaderMaterial;
        mesh: THREE.Mesh;
        sunPos: THREE.Vector3;
        sunId: string | null;
    }[] = [];
    private readonly detailNormal = makeDetailNormal();
    /** The GPU forge every world's cartography is drawn by; it owns the render
     *  targets, so disposing it frees the whole corpus of worlds. */
    private readonly forge: PlanetForge;
    /** Moons share a handful of regolith cartographies: at moon size no eye
     *  tells two craterscapes apart, and it spares a world's forging per moon. */
    private readonly moonAssets = new Map<number, PlanetAssets>();
    private readonly bulges: { sprite: THREE.Sprite; base: number }[] = [];
    private readonly textureJobs: (() => void)[] = [];
    private texturesPending = 0;
    private readonly particleSprite = makeParticleSprite();
    private readonly discs: THREE.Points[] = [];
    private readonly controllers: THREE.XRTargetRaySpace[] = [];
    private vrButton: HTMLElement | null = null;
    private hovered: THREE.Object3D | null = null;
    private panel: THREE.Mesh | null = null;
    private panelState: PanelState | null = null;
    private panelButtons: THREE.Mesh[] = [];
    private panelLinks: PanelLinkRect[] = [];
    private panelVisible = 20;
    private readonly bodyIds: Set<string>;
    private readonly filterTweens: {
        mesh: THREE.Mesh;
        from: number;
        to: number;
        start: number;
    }[] = [];
    /** Host hook: told when an immersive session starts or ends. */
    onXrPresence: ((presenting: boolean) => void) | null = null;
    /** Host hook: world-generation progress (done, total), for a loading veil. */
    onWorldProgress: ((done: number, total: number) => void) | null = null;
    /** Host hook: the LATCHED galaxy context. Set by selecting any of a
     *  galaxy's bodies or entering its sphere; switched by entering another
     *  galaxy; cleared only by flyHome or clearGalaxyContext. Zooming out
     *  never drops it, so a focus survives the wide view. */
    onGalaxyContext: ((name: string | null) => void) | null = null;
    private galaxyContext: string | null = null;
    private contextCheckAt = 0;
    private worldsTotal = 0;
    private readonly sunOffsets = new Map<string, SunOffset>();
    private readonly sunStreaks: {
        material: THREE.SpriteMaterial;
        mesh: THREE.Mesh;
        base: number;
        seed: number;
    }[] = [];
    private readonly bonds: {
        line: THREE.Line;
        geometry: THREE.BufferGeometry;
        fromId: string;
        toId: string;
    }[] = [];
    private readonly sunOfBody = new Map<string, string | null>();
    /** Reflow inertia: how far behind its sun's motion each orbiter trails
     *  (seconds), so a gliding system stretches instead of moving rigidly. */
    private readonly reflowLag = new Map<string, number>();
    private tween: CameraTween | null = null;
    private followId: string | null = null;
    private elapsed = 0;
    private frames = 0;
    private clicks = 0;
    private lastSelected: string | null = null;
    private disposed = false;

    constructor(container: HTMLElement, model: UniverseModel, onSelect: (body: SceneBody) => void) {
        this.container = container;
        this.model = model;
        this.onSelect = onSelect;
        this.resolve = createPositionResolver(model);
        this.bodyIds = new Set(model.bodies.map((b) => b.id));
        for (const body of model.bodies) {
            this.sunOfBody.set(body.id, this.governingSun(body)?.id ?? null);
        }
        for (const body of model.bodies) {
            if (!body.orbit && body.kind !== 'moon') {
                continue;
            }
            if ((body.kind === 'moon' || body.kind === 'ring') && body.moonOf) {
                const parent = model.bodies.find((b) => b.id === body.moonOf);
                const parentLag = parent?.orbit ? Math.min(parent.orbit.radius * 0.6, 0.15) : 0;
                this.reflowLag.set(body.id, parentLag + (body.kind === 'moon' ? 0.05 : 0));
            } else if (body.orbit) {
                this.reflowLag.set(body.id, Math.min(body.orbit.radius * 0.6, 0.15));
            }
        }

        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            preserveDrawingBuffer: true,
        });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(container.clientWidth, container.clientHeight, false);
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.1;
        this.renderer.xr.enabled = true;
        container.appendChild(this.renderer.domElement);
        this.renderer.domElement.style.width = '100%';
        this.renderer.domElement.style.height = '100%';
        this.renderer.domElement.style.display = 'block';
        this.forge = new PlanetForge(this.renderer);

        this.camera = new THREE.PerspectiveCamera(
            58,
            container.clientWidth / Math.max(container.clientHeight, 1),
            0.004,
            120,
        );
        this.camera.position.copy(HOME_POSITION);

        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.target.copy(HOME_TARGET);
        this.controls.enableDamping = true;
        this.controls.maxDistance = 20;
        this.controls.minDistance = 0.03;

        this.scene.background = new THREE.Color('#02040a');
        this.scene.add(new THREE.AmbientLight('#94a3c8', 0.22));
        const key = new THREE.DirectionalLight('#fff7ed', 1.2);
        key.position.set(4, 7, 3);
        this.scene.add(key);
        const rim = new THREE.DirectionalLight('#7dd3fc', 0.35);
        rim.position.set(-5, -2, -4);
        this.scene.add(rim);
        // A neutral environment so metals (door stations) have something to
        // reflect; planets use their own shader and ignore it.
        const pmrem = new THREE.PMREMGenerator(this.renderer);
        this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
        this.scene.environmentIntensity = 0.65;
        pmrem.dispose();

        this.composer = new EffectComposer(this.renderer);
        this.composer.addPass(new RenderPass(this.scene, this.camera));
        this.composer.addPass(
            new UnrealBloomPass(
                new THREE.Vector2(container.clientWidth, container.clientHeight),
                0.55,
                0.5,
                0.6,
            ),
        );
        this.composer.addPass(new OutputPass());

        this.buildStars();
        this.buildNebulae();
        this.buildGalaxies();
        this.buildStardustNebulae();
        this.buildBodies();
        this.setupXr();
        this.pumpTextureQueue();

        container.addEventListener('pointermove', this.onPointerMove);
        container.addEventListener('click', this.onClick);
        container.addEventListener('dblclick', this.onDoubleClick);

        this.resizeObserver = new ResizeObserver(() => this.onResize());
        this.resizeObserver.observe(container);

        this.renderer.setAnimationLoop(this.onFrame);
    }

    stats(): UniverseSceneStats & {
        frames: number;
        clicks: number;
        lastSelected: string | null;
    } {
        return {
            bodies: this.model.bodies.length,
            moons: this.model.bodies.filter((b) => b.kind === 'moon').length,
            galaxies: this.model.galaxies.length,
            nebulae: this.model.nebulae.length,
            xrEnabled: this.renderer.xr.enabled,
            bloom: true,
            panelOpen: this.panel !== null,
            texturesPending: this.texturesPending,
            frames: this.frames,
            clicks: this.clicks,
            lastSelected: this.lastSelected,
        };
    }

    /** Drive one frame synchronously: headless harnesses (hidden tabs, CI
     *  screenshot runs) have no requestAnimationFrame, but still need pixels. */
    renderOnce(): void {
        this.onFrame();
    }

    /** Luma/hue metrics from the framebuffer, for headless verification. */
    snapshot(): UniverseSnapshot {
        const sample = document.createElement('canvas');
        sample.width = 64;
        sample.height = 64;
        const ctx = sample.getContext('2d');
        if (!ctx) {
            return { meanLuma: 0, maxLuma: 0, brightFraction: 0, distinctHues: 0 };
        }
        ctx.drawImage(this.renderer.domElement, 0, 0, 64, 64);
        const data = ctx.getImageData(0, 0, 64, 64).data;
        let sum = 0;
        let max = 0;
        let bright = 0;
        const hues = new Set<number>();
        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
            sum += luma;
            max = Math.max(max, luma);
            if (luma > 140) {
                bright += 1;
            }
            const peak = Math.max(r, g, b);
            if (peak > 60 && peak - Math.min(r, g, b) > 28) {
                hues.add(Math.round(Math.atan2(Math.sqrt(3) * (g - b), 2 * r - g - b) * 6));
            }
        }
        const pixels = data.length / 4;
        return {
            meanLuma: sum / pixels,
            maxLuma: max,
            brightFraction: bright / pixels,
            distinctHues: hues.size,
        };
    }

    showDocument(title: string, meta: string, body: string, accent = '#38bdf8'): void {
        const lines = layoutDocument(body, (token) => (this.bodyIds.has(token) ? token : null));
        this.panelState = { title, meta, lines, scroll: 0, accent };
        this.renderPanel();
    }

    closePanel(): void {
        if (this.panel) {
            this.scene.remove(this.panel);
            disposeObject(this.panel);
            this.panel = null;
            this.panelButtons = [];
            this.panelState = null;
            this.panelLinks = [];
        }
    }

    /** Fly to a body by id and open it, as if clicked. The travel primitive
     *  behind every cross-reference link. Selecting a body latches its
     *  galaxy as the filter context immediately. */
    select(id: string): boolean {
        // Synthetic bodies (galaxy labels) live in byMesh, not the model.
        const body =
            this.model.bodies.find((b) => b.id === id) ??
            [...this.byMesh.values()].find((b) => b.id === id);
        if (!body) {
            return false;
        }
        if (body.galaxy) {
            this.setGalaxyContext(body.galaxy);
        }
        this.lastSelected = body.id;
        this.flyTo(body);
        this.onSelect(body);
        return true;
    }

    private setGalaxyContext(name: string | null): void {
        if (name !== this.galaxyContext) {
            this.galaxyContext = name;
            this.onGalaxyContext?.(name);
        }
    }

    /** Drop the latched galaxy context (the legend's explicit dismiss). */
    clearGalaxyContext(): void {
        this.setGalaxyContext(null);
    }

    /** Carter's astronomy: a planet can be bound to more than one star while
     *  belonging to one system. Show a selected body's bonds to the suns it
     *  cites beyond its home as faint light-lines. */
    showBonds(fromId: string, sunIds: string[]): void {
        this.clearBonds();
        const from = this.meshById.get(fromId);
        const body = from ? this.byMesh.get(from) : undefined;
        if (!from || !body) {
            return;
        }
        for (const sunId of sunIds) {
            if (!this.meshById.has(sunId)) {
                continue;
            }
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
            const line = new THREE.Line(
                geometry,
                new THREE.LineBasicMaterial({
                    color: new THREE.Color(body.color).lerp(new THREE.Color('#ffffff'), 0.4),
                    transparent: true,
                    opacity: 0.3,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                }),
            );
            line.name = `bond:${fromId}->${sunId}`;
            this.scene.add(line);
            this.bonds.push({ line, geometry, fromId, toId: sunId });
        }
    }

    /** A ship's flight plan, lit: one line per leg between the planets its
     *  licence names, tracking both ends live. Appends to the bonds shown. */
    showRoute(shipId: string): void {
        const mesh = this.meshById.get(shipId);
        const body = mesh ? this.byMesh.get(mesh) : undefined;
        const stops = body?.route?.stops ?? (body?.orbit ? [body.orbit.anchorId] : []);
        const legs: [string, string][] =
            stops.length >= 2
                ? stops.map((stop, i) => [stop, stops[(i + 1) % stops.length]])
                : stops.length === 1 && this.meshById.has(stops[0]) && body?.kind === 'agent'
                  ? [[shipId, stops[0]]]
                  : [];
        for (const [fromId, toId] of legs) {
            if (!this.meshById.has(fromId) || !this.meshById.has(toId)) {
                continue;
            }
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
            const line = new THREE.Line(
                geometry,
                new THREE.LineBasicMaterial({
                    color: new THREE.Color(body?.color ?? '#ffffff'),
                    transparent: true,
                    opacity: 0.55,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                }),
            );
            line.name = `route:${shipId}:${fromId}->${toId}`;
            this.scene.add(line);
            this.bonds.push({ line, geometry, fromId, toId });
        }
    }

    clearBonds(): void {
        for (const bond of this.bonds) {
            this.scene.remove(bond.line);
            bond.geometry.dispose();
            (bond.line.material as THREE.Material).dispose();
        }
        this.bonds.length = 0;
    }

    isPresenting(): boolean {
        return this.renderer.xr.isPresenting;
    }

    flyHome(): void {
        this.followId = null;
        this.setGalaxyContext(null);
        this.clearBonds();
        this.startTween(HOME_POSITION.clone(), HOME_TARGET.clone(), 1.1);
    }

    dispose(): void {
        this.disposed = true;
        this.renderer.setAnimationLoop(null);
        this.resizeObserver.disconnect();
        this.container.removeEventListener('pointermove', this.onPointerMove);
        this.container.removeEventListener('click', this.onClick);
        this.container.removeEventListener('dblclick', this.onDoubleClick);
        for (const controller of this.controllers) {
            controller.removeEventListener('selectstart', this.onControllerSelect);
        }
        this.closePanel();
        disposeObject(this.scene);
        this.forge.dispose();
        this.composer.dispose();
        this.controls.dispose();
        this.renderer.dispose();
        this.vrButton?.remove();
        this.renderer.domElement.remove();
    }

    private buildStars(): void {
        // Two depths of soft round stars; sprite-mapped points, never squares.
        const layers: [number, number, number, number][] = [
            [20260716, 2600, 0.055, 0.75],
            [20260717, 500, 0.13, 1.0],
        ];
        for (const [seed, count, size, opacity] of layers) {
            const rand = seededRandom(seed);
            const positions = new Float32Array(count * 3);
            const colors = new Float32Array(count * 3);
            const tint = new THREE.Color();
            for (let i = 0; i < positions.length; i += 3) {
                const r = 22 + rand() * 55;
                const theta = rand() * Math.PI * 2;
                const phi = Math.acos(2 * rand() - 1);
                positions[i] = r * Math.sin(phi) * Math.cos(theta);
                positions[i + 1] = r * Math.cos(phi);
                positions[i + 2] = r * Math.sin(phi) * Math.sin(theta);
                // Stellar palette: blue-white through amber, weighted white.
                const heat = rand();
                tint.setHSL(heat < 0.7 ? 0.58 : 0.08, 0.25 + rand() * 0.4, 0.7 + rand() * 0.28);
                colors[i] = tint.r;
                colors[i + 1] = tint.g;
                colors[i + 2] = tint.b;
            }
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            const stars = new THREE.Points(
                geometry,
                new THREE.PointsMaterial({
                    size,
                    map: this.particleSprite,
                    alphaTest: 0.01,
                    vertexColors: true,
                    transparent: true,
                    opacity,
                    sizeAttenuation: true,
                    depthWrite: false,
                    blending: THREE.AdditiveBlending,
                }),
            );
            stars.name = `stars:${seed}`;
            this.scene.add(stars);
        }

        // The galactic band: a dense inclined river of faint stars with warm
        // nebulosity, the thing that makes a sky read as a universe.
        const rand = seededRandom(0x9a1ac7);
        const count = 15000;
        const positions = new Float32Array(count * 3);
        const colors = new Float32Array(count * 3);
        const tint = new THREE.Color();
        const bandTilt = new THREE.Euler(0.42, 0, 0.28);
        const point = new THREE.Vector3();
        const gauss = (): number => (rand() + rand() + rand() - 1.5) / 1.5;
        for (let i = 0; i < count; i += 1) {
            const t = rand() * Math.PI * 2;
            const r = 20 + rand() * 46;
            point.set(r * Math.cos(t), gauss() * 3.4, r * Math.sin(t));
            point.applyEuler(bandTilt);
            positions[i * 3] = point.x;
            positions[i * 3 + 1] = point.y;
            positions[i * 3 + 2] = point.z;
            const warm = rand();
            tint.setHSL(warm < 0.6 ? 0.09 : 0.58, 0.2 + rand() * 0.3, 0.55 + rand() * 0.3);
            colors[i * 3] = tint.r;
            colors[i * 3 + 1] = tint.g;
            colors[i * 3 + 2] = tint.b;
        }
        const bandGeometry = new THREE.BufferGeometry();
        bandGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        bandGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        const band = new THREE.Points(
            bandGeometry,
            new THREE.PointsMaterial({
                size: 0.075,
                map: this.particleSprite,
                alphaTest: 0.01,
                vertexColors: true,
                transparent: true,
                opacity: 0.75,
                sizeAttenuation: true,
                depthWrite: false,
                blending: THREE.AdditiveBlending,
            }),
        );
        band.name = 'stars:milkyway';
        this.scene.add(band);
        for (let i = 0; i < 7; i += 1) {
            const cloud = new THREE.Sprite(
                new THREE.SpriteMaterial({
                    map: makeNebulaTexture(0x77e1 + i, i % 2 === 0 ? '#c9a878' : '#7d9cc9'),
                    transparent: true,
                    opacity: 0.14,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                    rotation: rand() * Math.PI,
                }),
            );
            const t = (i / 7) * Math.PI * 2;
            const r = 32 + rand() * 26;
            point.set(r * Math.cos(t), gauss() * 3, r * Math.sin(t));
            point.applyEuler(bandTilt);
            cloud.position.copy(point);
            cloud.scale.setScalar(14 + rand() * 12);
            cloud.name = `nebula:band-${i}`;
            this.scene.add(cloud);
        }
    }

    private buildNebulae(): void {
        const rand = seededRandom(777);
        this.model.galaxies.forEach((galaxy, i) => {
            const sprite = new THREE.Sprite(
                new THREE.SpriteMaterial({
                    map: makeNebulaTexture(galaxy.seed ^ (i + 1), galaxy.color),
                    transparent: true,
                    opacity: 0.16,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                    rotation: rand() * Math.PI,
                }),
            );
            // Background dressing lives far out of the flight plane, so the
            // camera never sits inside a screen-filling additive wash.
            const spread = 6 + rand() * 3;
            sprite.position.set(
                galaxy.center[0] * 3.2 + (rand() - 0.5) * 4,
                galaxy.center[1] + 3.5 + rand() * 3 + i,
                galaxy.center[2] * 3.2 + (rand() - 0.5) * 4 - 6,
            );
            sprite.scale.setScalar(spread);
            sprite.name = `nebula:${galaxy.name}`;
            this.scene.add(sprite);
        });
    }

    private buildGalaxies(): void {
        for (const galaxy of this.model.galaxies) {
            const rand = seededRandom(galaxy.seed);
            const maxR = galaxy.radius * 1.3;
            const count = 2400;
            const positions = new Float32Array(count * 3);
            const colors = new Float32Array(count * 3);
            const base = new THREE.Color(galaxy.color);
            const white = new THREE.Color('#fff7ed');
            const amber = new THREE.Color('#e8c9a0');
            const deep = base.clone().offsetHSL(0.06, 0.1, -0.18);
            const morphology = galaxy.morphology;
            const gauss = (): number => (rand() + rand() + rand() - 1.5) / 1.5;
            // Irregulars are a few displaced star-forming clumps.
            const clumps = Array.from({ length: 3 + Math.floor(rand() * 3) }, () => ({
                x: (rand() - 0.5) * maxR * 1.5,
                z: (rand() - 0.5) * maxR * 1.5,
                r: maxR * (0.18 + rand() * 0.22),
            }));
            for (let i = 0; i < count; i += 1) {
                const inBulge = morphology !== 'irregular' && i < count * 0.18;
                let x: number;
                let z: number;
                let y: number;
                let mixed: THREE.Color;
                if (inBulge) {
                    // Central bulge (or the whole body, for ellipticals).
                    const r = maxR * 0.22 * Math.cbrt(rand());
                    const theta = rand() * Math.PI * 2;
                    const phi = Math.acos(2 * rand() - 1);
                    x = r * Math.sin(phi) * Math.cos(theta);
                    y = r * Math.cos(phi) * 0.6;
                    z = r * Math.sin(phi) * Math.sin(theta);
                    mixed = white.clone().lerp(base, rand() * 0.4);
                } else if (morphology === 'elliptical') {
                    // Old smooth ellipsoid: amber population, no arms.
                    x = gauss() * maxR * 0.62;
                    y = gauss() * maxR * 0.36;
                    z = gauss() * maxR * 0.5;
                    mixed = amber.clone().lerp(base, rand() * 0.35);
                } else if (morphology === 'irregular') {
                    // Clumpy star-forming chaos plus a loose field.
                    if (rand() < 0.7) {
                        const clump = clumps[Math.floor(rand() * clumps.length)];
                        x = clump.x + gauss() * clump.r;
                        z = clump.z + gauss() * clump.r;
                        y = gauss() * clump.r * 0.4;
                    } else {
                        x = (rand() - 0.5) * maxR * 2;
                        z = (rand() - 0.5) * maxR * 2;
                        y = gauss() * 0.12;
                    }
                    mixed = base.clone().lerp(white, rand() * 0.8);
                } else {
                    // Spiral or barred: logarithmic arms with dust scatter;
                    // barred galaxies grow a central bar the arms hang off.
                    const r = maxR * (0.18 + 0.82 * Math.sqrt(rand()));
                    if (morphology === 'barred' && rand() < 0.22) {
                        const along = (rand() - 0.5) * maxR * 0.9;
                        x = along;
                        z = gauss() * maxR * 0.07;
                        y = gauss() * 0.05;
                        mixed = white.clone().lerp(base, rand() * 0.5);
                    } else {
                        const arm = rand() < 0.5 ? 0 : Math.PI;
                        const barOffset = morphology === 'barred' ? 0.45 : 0;
                        const startR = morphology === 'barred' ? maxR * 0.42 : 0;
                        const rr = Math.max(r, startR * (0.9 + rand() * 0.2));
                        const twist = ((rr - startR) / (maxR - startR + 0.001)) * 4.2;
                        const scatter = (rand() - 0.5) * (0.28 + (rr / maxR) * 0.75);
                        const theta = arm + barOffset + twist + scatter;
                        const thickness = (rand() - 0.5) * 0.07 * (1.7 - rr / maxR);
                        x = rr * Math.cos(theta);
                        y = thickness;
                        z = rr * Math.sin(theta);
                        const toRim = rr / maxR;
                        mixed =
                            rand() < 0.12
                                ? deep.clone()
                                : base.clone().lerp(white, rand() * (0.75 - toRim * 0.4));
                    }
                }
                positions[i * 3] = x;
                positions[i * 3 + 1] = y;
                positions[i * 3 + 2] = z;
                colors[i * 3] = mixed.r;
                colors[i * 3 + 1] = mixed.g;
                colors[i * 3 + 2] = mixed.b;
            }
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            const disc = new THREE.Points(
                geometry,
                new THREE.PointsMaterial({
                    size: 0.009,
                    map: this.particleSprite,
                    alphaTest: 0.01,
                    vertexColors: true,
                    transparent: true,
                    opacity: 0.68,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                }),
            );
            disc.position.set(...galaxy.center);
            disc.rotation.set(galaxy.tilt[0], 0, galaxy.tilt[1]);
            disc.name = `galaxy:${galaxy.name}`;
            this.scene.add(disc);
            this.discs.push(disc);

            const bulgeGlow = new THREE.Sprite(
                new THREE.SpriteMaterial({
                    map: radialGlowTexture(galaxy.color, 0.4),
                    transparent: true,
                    opacity: 0.14,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                }),
            );
            bulgeGlow.scale.setScalar(maxR * 0.45);
            bulgeGlow.position.set(...galaxy.center);
            bulgeGlow.name = `bulge:${galaxy.name}`;
            this.scene.add(bulgeGlow);
            this.bulges.push({ sprite: bulgeGlow, base: 0.3 });

            const label = makeTextSprite(galaxy.name, 48, galaxy.color);
            label.position.set(
                galaxy.center[0],
                galaxy.center[1] + galaxy.radius * 1.25 + 0.22,
                galaxy.center[2],
            );
            this.scene.add(label);
            // The label is a body too: clicking a galaxy's name flies to it
            // and opens its GALAXY.md on the reading panel.
            this.pickables.push(label);
            this.byMesh.set(label, {
                id: `galaxy:${galaxy.name}`,
                kind: 'galaxy',
                label: galaxy.name,
                galaxy: galaxy.name,
                color: galaxy.color,
                size: galaxy.radius,
                seed: galaxy.seed,
                node: null,
            });
        }
    }

    /** Stardust nebulae: each territory under study is a dim cloud beyond the
     *  earned scatter (REF-Forge: unearned renders visible, second-class,
     *  honest). A soft nebulosity sprite gives it visible mass and dim additive
     *  points give it grain; both peak well under the bloom threshold and carry
     *  no corona, so a nebula reads as present but never as bright as an earned
     *  galaxy. Static by design: nothing here ticks or allocates per frame. */
    private buildStardustNebulae(): void {
        for (const nebula of this.model.nebulae) {
            const rand = seededRandom(nebula.seed);
            const count = Math.min(150 + nebula.noteCount * 22, 420);
            const positions = new Float32Array(count * 3);
            const colors = new Float32Array(count * 3);
            const base = new THREE.Color(nebula.color);
            const tint = new THREE.Color();
            const gauss = (): number => (rand() + rand() + rand() - 1.5) / 1.5;
            // A wisp: a loose field plus a few denser clumps, never a disc.
            const clumps = Array.from({ length: 3 + Math.floor(rand() * 3) }, () => ({
                x: (rand() - 0.5) * nebula.radius * 1.4,
                y: (rand() - 0.5) * nebula.radius * 0.6,
                z: (rand() - 0.5) * nebula.radius * 1.4,
                r: nebula.radius * (0.25 + rand() * 0.3),
            }));
            for (let i = 0; i < count; i += 1) {
                if (rand() < 0.35) {
                    positions[i * 3] = gauss() * nebula.radius;
                    positions[i * 3 + 1] = gauss() * nebula.radius * 0.55;
                    positions[i * 3 + 2] = gauss() * nebula.radius;
                } else {
                    const clump = clumps[Math.floor(rand() * clumps.length)];
                    positions[i * 3] = clump.x + gauss() * clump.r;
                    positions[i * 3 + 1] = clump.y + gauss() * clump.r * 0.6;
                    positions[i * 3 + 2] = clump.z + gauss() * clump.r;
                }
                tint.copy(base).offsetHSL(
                    (rand() - 0.5) * 0.04,
                    -0.05 * rand(),
                    (rand() - 0.3) * 0.16,
                );
                colors[i * 3] = tint.r;
                colors[i * 3 + 1] = tint.g;
                colors[i * 3 + 2] = tint.b;
            }
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            // Soft nebulosity: one muted sprite gives the territory visible
            // mass. Additive but low-opacity, so it peaks far under the bloom
            // threshold - a faint slate haze, never a lit core.
            const haze = new THREE.Sprite(
                new THREE.SpriteMaterial({
                    map: makeNebulaTexture(nebula.seed ^ 0x5eed, nebula.color),
                    transparent: true,
                    opacity: 0.34,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                    rotation: rand() * Math.PI,
                }),
            );
            haze.position.set(...nebula.center);
            haze.scale.setScalar(nebula.radius * 3.0);
            haze.name = `stardust-haze:${nebula.name}`;
            this.scene.add(haze);

            const cloud = new THREE.Points(
                geometry,
                new THREE.PointsMaterial({
                    size: 0.05,
                    map: this.particleSprite,
                    alphaTest: 0.01,
                    vertexColors: true,
                    transparent: true,
                    opacity: 0.55,
                    sizeAttenuation: true,
                    depthWrite: false,
                    blending: THREE.AdditiveBlending,
                }),
            );
            cloud.position.set(...nebula.center);
            cloud.name = `stardust:${nebula.name}`;
            this.scene.add(cloud);

            const body: SceneBody = {
                id: `nebula:${nebula.name}`,
                kind: 'nebula',
                label: nebula.name,
                galaxy: null,
                color: nebula.color,
                size: nebula.radius,
                seed: nebula.seed,
                node: null,
            };
            // An invisible proxy sphere makes the cloud selectable through
            // the existing raycast path (clouds of Points have no clean hit).
            const proxy = new THREE.Mesh(
                new THREE.SphereGeometry(nebula.radius * 0.6, 12, 8),
                new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
            );
            proxy.position.set(...nebula.center);
            proxy.name = `body:nebula:${nebula.name}`;
            this.scene.add(proxy);
            this.pickables.push(proxy);
            this.byMesh.set(proxy, body);
            this.meshById.set(body.id, proxy);

            const label = makeTextSprite(nebula.name, 30, '#8b93a3');
            label.material.opacity = 0.55;
            label.position.set(
                nebula.center[0],
                nebula.center[1] + nebula.radius * 0.8 + 0.18,
                nebula.center[2],
            );
            this.scene.add(label);
            this.pickables.push(label);
            this.byMesh.set(label, body);
        }
    }

    private buildBodies(): void {
        for (const body of this.model.bodies) {
            const mesh = this.buildBodyMesh(body);
            const [x, y, z] = this.resolve(body.id, 0);
            mesh.position.set(x, y, z);
            mesh.name = `body:${body.id}`;
            this.scene.add(mesh);
            this.pickables.push(mesh);
            this.byMesh.set(mesh, body);
            this.meshById.set(body.id, mesh);

            const labelSize = body.kind === 'sun' ? 24 : body.kind === 'hub' ? 30 : 18;
            const label = makeTextSprite(body.label, labelSize, '#e2e8f0');
            label.position.set(x, y + body.size + 0.05, z);
            label.visible = false;
            this.scene.add(label);
            this.labels.set(mesh, label);
        }
    }

    private buildBodyMesh(body: SceneBody): THREE.Mesh {
        const rand = seededRandom(body.seed);
        if (body.kind === 'sun' || body.kind === 'hub') {
            // A star: animated granulation surface, a tight chromosphere, a
            // spiked astrophoto corona, and (for the bright ones) a nearby
            // anamorphic streak that fades with distance.
            const isHub = body.kind === 'hub';
            const material = makeSunMaterial(body.color, isHub ? 1.9 : (body.intensity ?? 1.25));
            this.sunMaterials.push(material);
            const mesh = new THREE.Mesh(new THREE.SphereGeometry(body.size, 48, 32), material);

            const chromosphere = new THREE.Sprite(
                new THREE.SpriteMaterial({
                    map: radialGlowTexture(body.color, 0.2),
                    transparent: true,
                    opacity: isHub ? 0.5 : 0.32,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                }),
            );
            chromosphere.scale.setScalar(body.size * (isHub ? 1.7 : 1.35));
            mesh.add(chromosphere);

            const corona = new THREE.Sprite(
                new THREE.SpriteMaterial({
                    map: makeSpikedCorona(body.seed, body.color),
                    transparent: true,
                    opacity: isHub ? 0.9 : 0.6,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                    rotation: rand() * Math.PI,
                }),
            );
            const base = body.size * (isHub ? 8.5 : 4.2 + rand() * 0.9);
            corona.scale.setScalar(base);
            mesh.add(corona);
            this.halos.push({ sprite: corona, base, seed: body.seed });

            // Dwarf stars are clean glows; only the bright ones flare, and
            // the flare lives near the camera (updated per frame).
            if (isHub || (body.intensity ?? 1.25) > 1.28) {
                const streakMaterial = new THREE.SpriteMaterial({
                    map: makeAnamorphicStreak(body.color),
                    transparent: true,
                    opacity: 0,
                    blending: THREE.AdditiveBlending,
                    depthWrite: false,
                    rotation: isHub ? 0 : (rand() - 0.5) * 0.3,
                });
                const streak = new THREE.Sprite(streakMaterial);
                streak.scale.set(
                    body.size * (isHub ? 18 : 8 + rand() * 5),
                    body.size * (isHub ? 4 : 2 + rand() * 0.8),
                    1,
                );
                mesh.add(streak);
                this.sunStreaks.push({
                    material: streakMaterial,
                    mesh,
                    base: isHub ? 0.85 : 0.4 + ((body.intensity ?? 1.25) - 1.28) * 1.1,
                    seed: body.seed,
                });
            }
            return mesh;
        }
        if (body.kind === 'door') {
            // A door is a station: dense metal ring with lit portholes and a
            // shimmering portal membrane you could fly through.
            const windowStrip = makeWindowStrip(body.seed);
            windowStrip.repeat.set(4, 1);
            const station = new THREE.Mesh(
                new THREE.TorusGeometry(body.size * 1.25, body.size * 0.3, 22, 72),
                new THREE.MeshStandardMaterial({
                    color: '#9aa2b1',
                    roughness: 0.34,
                    metalness: 0.88,
                    emissive: '#ffffff',
                    emissiveMap: windowStrip,
                    emissiveIntensity: 1.6,
                }),
            );
            const rim = new THREE.Mesh(
                new THREE.TorusGeometry(body.size * 1.25, body.size * 0.06, 10, 72),
                new THREE.MeshBasicMaterial({
                    color: body.color,
                    toneMapped: false,
                }),
            );
            rim.scale.setScalar(1.26);
            station.add(rim);
            const portalMaterial = makePortalMaterial(body.color);
            this.portalMaterials.push(portalMaterial);
            const portal = new THREE.Mesh(
                new THREE.CircleGeometry(body.size * 1.02, 48),
                portalMaterial,
            );
            station.add(portal);
            station.rotation.set(rand() * Math.PI, rand() * Math.PI, 0);
            this.spins.set(station, 0.18 + rand() * 0.22);
            return station;
        }
        if (body.kind === 'agent') {
            return this.buildShip(body);
        }
        if (body.kind === 'ring') {
            // A ring is a folder: the material a planet holds, one band per
            // file, tilted with its own inclination and turning slowly.
            const ring = new THREE.Mesh(
                new THREE.RingGeometry(body.size * 0.56, body.size, 96, 1),
                new THREE.MeshBasicMaterial({
                    map: makeRingTexture(body.seed, body.files?.length ?? 1),
                    color: body.color,
                    transparent: true,
                    opacity: 0.85,
                    side: THREE.DoubleSide,
                    depthWrite: false,
                }),
            );
            ring.rotation.set(Math.PI / 2 + (body.orbit?.incline ?? 0), 0, rand() * Math.PI);
            this.spins.set(ring, 0.04 + rand() * 0.05);
            return ring;
        }
        // Planets and moons: sphere-sampled cartography with real normals,
        // lit by their own sun; a dark placeholder until the assets land.
        const isMoon = body.kind === 'moon';
        // Visible before its cartography lands: a dim slate world, never a
        // black hole in space.
        const placeholder = new THREE.MeshStandardMaterial({
            color: '#4a5468',
            roughness: 0.9,
            metalness: 0,
            emissive: '#232a3a',
            emissiveIntensity: 0.55,
        });
        const mesh: THREE.Mesh = new THREE.Mesh(
            new THREE.SphereGeometry(body.size, isMoon ? 40 : 56, isMoon ? 26 : 36),
            placeholder,
        );
        mesh.rotation.z = (rand() - 0.5) * 0.7;
        this.spins.set(mesh, 0.25 + rand() * 0.5);
        this.texturesPending += 1;
        this.textureJobs.push(() => {
            const assets = isMoon
                ? this.moonCartography(body.seed)
                : this.forge.forge(
                      body.seed,
                      archetypeOf(body.seed),
                      cartographyWidth(DEFAULT_CARTOGRAPHY_QUALITY),
                  );
            const sunPos = this.governingSunPos(body);
            const material = makePlanetMaterial(
                assets,
                this.detailNormal,
                sunPos.clone().sub(mesh.position).normalize(),
                body.color,
            );
            mesh.material = material;
            placeholder.dispose();
            this.planetShades.push({
                material,
                mesh,
                sunPos,
                sunId: this.sunOfBody.get(body.id) ?? null,
            });
            this.texturesPending -= 1;
        });
        return mesh;
    }

    /** An agent is a ship (REF-Universe par. 3): a crewed vessel flying the
     *  route of the planets its licence names. The hull lies along +Z so
     *  lookAt() points its nose down the leg it is flying; the fresh-eyes
     *  reviewer is the outsider's cutter, dark-hulled with a pale lamp. */
    private buildShip(body: SceneBody): THREE.Mesh {
        const rand = seededRandom(body.seed ^ 0x5419);
        const outsider = body.node?.fresh_eyes === true;
        const size = body.size;
        const hullColor = outsider ? '#232938' : '#b7bfcd';
        const lamp = outsider ? '#dbe4f0' : body.color;
        const hullGeometry = new THREE.CapsuleGeometry(size * 0.42, size * 1.5, 4, 12);
        hullGeometry.rotateX(Math.PI / 2);
        const hull = new THREE.Mesh(
            hullGeometry,
            new THREE.MeshStandardMaterial({
                color: hullColor,
                roughness: outsider ? 0.55 : 0.3,
                metalness: outsider ? 0.6 : 0.85,
            }),
        );
        // Nose cone forward, two fins aft, a cockpit above the bow.
        const noseGeometry = new THREE.ConeGeometry(size * 0.42, size * 0.8, 12);
        noseGeometry.rotateX(Math.PI / 2);
        const nose = new THREE.Mesh(noseGeometry, hull.material);
        nose.position.z = size * 1.15;
        hull.add(nose);
        for (const side of [-1, 1]) {
            const fin = new THREE.Mesh(
                new THREE.BoxGeometry(size * 0.9, size * 0.08, size * 0.5),
                hull.material,
            );
            fin.position.set(side * size * 0.55, 0, -size * 0.55);
            fin.rotation.z = side * 0.25;
            hull.add(fin);
        }
        const cockpit = new THREE.Mesh(
            new THREE.SphereGeometry(size * 0.22, 12, 8),
            new THREE.MeshBasicMaterial({ color: lamp, toneMapped: false }),
        );
        cockpit.position.set(0, size * 0.38, size * 0.45);
        hull.add(cockpit);
        // The drive glow aft, in the crew's colour: what you see of a ship
        // from across a system is its engine.
        const drive = new THREE.Sprite(
            new THREE.SpriteMaterial({
                map: radialGlowTexture(lamp, 0.25),
                transparent: true,
                opacity: outsider ? 0.55 : 0.85,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            }),
        );
        drive.position.z = -size * 1.05;
        drive.scale.setScalar(size * (1.6 + rand() * 0.4));
        hull.add(drive);
        this.ships.push({ mesh: hull, id: body.id });
        return hull;
    }

    private moonCartography(seed: number): PlanetAssets {
        const variant = seed % MOON_VARIANTS;
        let assets = this.moonAssets.get(variant);
        if (!assets) {
            assets = this.forge.forge(
                hashSeed(`moon-variant:${variant}`),
                'regolith',
                cartographyWidth('moon'),
            );
            this.moonAssets.set(variant, assets);
        }
        return assets;
    }

    /** The sun a body belongs to: walk the anchor chain (moon to planet to
     *  sun). Null for hubs, suns themselves, and galaxy-anchored strays. */
    private governingSun(body: SceneBody): SceneBody | null {
        let current: SceneBody | undefined = body;
        for (let hops = 0; hops < 4 && current; hops += 1) {
            const anchorId: string | undefined = current.orbit?.anchorId ?? current.moonOf;
            if (!anchorId || anchorId.startsWith('galaxy:')) {
                return null;
            }
            const anchor: SceneBody | undefined = this.model.bodies.find((b) => b.id === anchorId);
            if (!anchor) {
                return null;
            }
            if (anchor.kind === 'sun') {
                return anchor;
            }
            current = anchor;
        }
        return null;
    }

    /** Where this body's light comes from; galaxy-anchored strays are lit by
     *  the hub. */
    private governingSunPos(body: SceneBody): THREE.Vector3 {
        const sun = this.governingSun(body);
        if (sun?.position) {
            return new THREE.Vector3(...sun.position);
        }
        return new THREE.Vector3(0, 1.5, 0);
    }

    /** Focus a GALAXY: filters apply only to the scoped galaxy's bodies (a
     *  galaxy owns its domain vocabulary); the rest of the universe stays
     *  visible. No scope means no filtering. Bodies scale, never pop. */
    applyFilter(filter: {
        galaxy: string | null;
        domains: string[] | null;
        showSkills: boolean;
        showAgents: boolean;
        showDoors: boolean;
    }): void {
        const domainOk = (domain: string | null | undefined): boolean =>
            filter.domains === null || filter.domains.includes(domain ?? '');
        for (const mesh of this.meshById.values()) {
            const body = this.byMesh.get(mesh);
            if (!body) {
                continue;
            }
            let visible = true;
            const inScope = filter.galaxy !== null && body.galaxy === filter.galaxy;
            if (inScope && body.kind === 'sun') {
                visible = domainOk(body.node?.domain);
            } else if (
                inScope &&
                (body.kind === 'planet' ||
                    body.kind === 'moon' ||
                    body.kind === 'ring' ||
                    body.kind === 'agent' ||
                    body.kind === 'door')
            ) {
                const kindOn =
                    body.kind === 'door'
                        ? filter.showDoors
                        : body.kind === 'agent'
                          ? filter.showAgents
                          : filter.showSkills;
                const sun = this.governingSun(body);
                visible = kindOn && (sun ? domainOk(sun.node?.domain) : filter.domains === null);
            }
            const currentlyShown = mesh.visible && mesh.scale.x > 0.5;
            if (visible === currentlyShown) {
                continue;
            }
            const existing = this.filterTweens.findIndex((t) => t.mesh === mesh);
            if (existing >= 0) {
                this.filterTweens.splice(existing, 1);
            }
            if (visible) {
                mesh.visible = true;
                if (mesh.scale.x > 0.99) {
                    mesh.scale.setScalar(0.001);
                }
            }
            this.filterTweens.push({
                mesh,
                from: mesh.scale.x,
                to: visible ? 1 : 0.001,
                start: this.elapsed,
            });
            if (!visible) {
                const label = this.labels.get(mesh);
                if (label) {
                    label.visible = false;
                }
                if (this.hovered === mesh) {
                    this.hovered = null;
                    this.container.style.cursor = 'default';
                }
            }
        }
        this.reflowSuns(filter);
    }

    /** Whether a body currently shows (filters considered); travel uses this
     *  to clear a filter that would land the camera on nothing. */
    isBodyVisible(id: string): boolean {
        const mesh = this.meshById.get(id);
        return !!mesh && mesh.visible && mesh.scale.x > 0.5;
    }

    /** Under an active domain focus, the surviving suns of the scoped galaxy
     *  re-seat by phyllotaxis over their own count, and every planet, moon,
     *  and door glides along with its sun: the 2D map's re-flow, in space. */
    private reflowSuns(filter: { galaxy: string | null; domains: string[] | null }): void {
        const targets = new Map<string, THREE.Vector3>();
        const galaxy = filter.galaxy
            ? this.model.galaxies.find((g) => g.name === filter.galaxy)
            : undefined;
        if (galaxy && filter.domains !== null) {
            const suns = this.model.bodies.filter(
                (b) => b.kind === 'sun' && b.galaxy === galaxy.name,
            );
            const visible = suns.filter((s) => filter.domains!.includes(s.node?.domain ?? ''));
            if (visible.length > 0 && visible.length < suns.length) {
                const goldenAngle = Math.PI * (3 - Math.sqrt(5));
                const radius = Math.min(galaxyDiscRadius(visible.length), galaxy.radius);
                const [tx, tz] = galaxy.tilt;
                visible.forEach((sun, i) => {
                    if (!sun.position) {
                        return;
                    }
                    const rand = seededRandom(sun.seed);
                    const r = radius * 0.92 * Math.sqrt((i + 0.6) / visible.length);
                    const theta = i * goldenAngle + rand() * 0.22;
                    const x0 = r * Math.cos(theta);
                    const y0 = (rand() - 0.5) * 0.16;
                    const z0 = r * Math.sin(theta);
                    const x1 = x0 * Math.cos(tz) - y0 * Math.sin(tz);
                    const y1 = x0 * Math.sin(tz) + y0 * Math.cos(tz);
                    const y2 = y1 * Math.cos(tx) - z0 * Math.sin(tx);
                    const z2 = y1 * Math.sin(tx) + z0 * Math.cos(tx);
                    targets.set(
                        sun.id,
                        new THREE.Vector3(
                            galaxy.center[0] + x1 - sun.position[0],
                            galaxy.center[1] + y2 - sun.position[1],
                            galaxy.center[2] + z2 - sun.position[2],
                        ),
                    );
                });
            }
        }
        const ids = new Set([...this.sunOffsets.keys(), ...targets.keys()]);
        const zero = new THREE.Vector3();
        for (const id of ids) {
            const target = targets.get(id) ?? zero;
            const entry = this.sunOffsets.get(id);
            if (entry) {
                if (entry.to.distanceToSquared(target) > 1e-8) {
                    entry.from.copy(entry.current);
                    entry.to.copy(target);
                    entry.start = this.elapsed;
                }
            } else {
                this.sunOffsets.set(id, {
                    current: new THREE.Vector3(),
                    from: new THREE.Vector3(),
                    to: target.clone(),
                    start: this.elapsed,
                });
            }
        }
    }

    /** Labels keep a constant size on screen: a moon's name read from a
     *  hand's breadth away is the same text as a sun's from across the hall,
     *  and it sits just clear of the body whatever the body's size. */
    private layoutLabels(): void {
        const viewportHeight = Math.max(this.container.clientHeight, 1);
        const worldPerPixelAtUnit =
            (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))) / viewportHeight;
        for (const [mesh, label] of this.labels) {
            if (!label.visible) {
                continue;
            }
            const body = this.byMesh.get(mesh);
            const px = label.userData as { width: number; height: number };
            const worldPerPixel =
                this.camera.position.distanceTo(mesh.position) * worldPerPixelAtUnit;
            const width = px.width * 0.5 * worldPerPixel;
            const height = px.height * 0.5 * worldPerPixel;
            label.scale.set(width, height, 1);
            label.position.set(
                mesh.position.x,
                mesh.position.y + (body?.size ?? 0) + height * 0.5 + 6 * worldPerPixel,
                mesh.position.z,
            );
        }
    }

    /** Forge worlds a couple per macrotask (REF-ThreeJS section 11): each job
     *  submits its GPU passes and returns, so the corpus lands in a moment
     *  while the main thread stays free and the host's loading veil tracks the
     *  progress. */
    private pumpTextureQueue(): void {
        this.worldsTotal = this.textureJobs.length;
        const step = (): void => {
            if (this.disposed) {
                return;
            }
            for (let i = 0; i < 2; i += 1) {
                const job = this.textureJobs.shift();
                if (!job) {
                    this.onWorldProgress?.(this.worldsTotal, this.worldsTotal);
                    return;
                }
                job();
            }
            this.onWorldProgress?.(this.worldsTotal - this.textureJobs.length, this.worldsTotal);
            setTimeout(step, 0);
        };
        setTimeout(step, 0);
    }

    private setupXr(): void {
        for (const index of [0, 1]) {
            const controller = this.renderer.xr.getController(index);
            controller.addEventListener('selectstart', this.onControllerSelect);
            const rayGeometry = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0, 0, 0),
                new THREE.Vector3(0, 0, -5),
            ]);
            const ray = new THREE.Line(
                rayGeometry,
                new THREE.LineBasicMaterial({ color: '#a5b4fc', transparent: true, opacity: 0.7 }),
            );
            controller.add(ray);
            this.scene.add(controller);
            this.controllers.push(controller);
        }
        // The host swaps the DOM reading panel for the in-scene one when a
        // headset session starts, and back when it ends.
        this.renderer.xr.addEventListener('sessionstart', () => {
            this.onXrPresence?.(true);
        });
        this.renderer.xr.addEventListener('sessionend', () => {
            this.onXrPresence?.(false);
        });
        // No dead chrome: the button exists only where a headset session can.
        void navigator.xr?.isSessionSupported('immersive-vr').then((supported) => {
            if (!supported || this.disposed) {
                return;
            }
            this.vrButton = VRButton.createButton(this.renderer);
            this.vrButton.style.position = 'absolute';
            this.vrButton.style.bottom = '14px';
            this.container.appendChild(this.vrButton);
        });
    }

    private readonly onFrame = (): void => {
        if (this.disposed) {
            return;
        }
        this.frames += 1;
        const now = performance.now();
        const dt = this.lastTime === null ? 0.016 : Math.min((now - this.lastTime) / 1000, 0.1);
        this.lastTime = now;
        this.elapsed += dt;

        // Re-seat offsets (filter reflow) ease over 0.9s. Suns lead; their
        // retinues evaluate the same tween slightly in the past (inertia).
        const offsetEase = (offset: SunOffset, lag: number, out: THREE.Vector3): void => {
            const raw = Math.min(Math.max((this.elapsed - offset.start - lag) / 0.9, 0), 1);
            const eased = raw < 0.5 ? 4 * raw ** 3 : 1 - (-2 * raw + 2) ** 3 / 2;
            out.lerpVectors(offset.from, offset.to, eased);
        };
        for (const [id, offset] of this.sunOffsets) {
            offsetEase(offset, 0, offset.current);
            const mesh = this.meshById.get(id);
            const body = mesh ? this.byMesh.get(mesh) : undefined;
            if (mesh && body?.position) {
                mesh.position.set(...body.position).add(offset.current);
                const label = this.labels.get(mesh);
                label?.position.set(
                    mesh.position.x,
                    mesh.position.y + body.size + 0.05,
                    mesh.position.z,
                );
            }
            // Keep the entry alive until the laggiest follower has settled.
            const raw = (this.elapsed - offset.start) / 0.9;
            if (raw >= 1.3 && offset.to.lengthSq() < 1e-8) {
                this.sunOffsets.delete(id);
            }
        }
        const lagged = new THREE.Vector3();
        for (const [id, mesh] of this.meshById) {
            const body = this.byMesh.get(mesh);
            if (body?.orbit) {
                const [x, y, z] = this.resolve(id, this.elapsed);
                mesh.position.set(x, y, z);
                const sunId = this.sunOfBody.get(id);
                const offset = sunId ? this.sunOffsets.get(sunId) : undefined;
                if (offset) {
                    offsetEase(offset, this.reflowLag.get(id) ?? 0, lagged);
                    mesh.position.add(lagged);
                }
                const label = this.labels.get(mesh);
                label?.position.set(
                    mesh.position.x,
                    mesh.position.y + body.size + 0.05,
                    mesh.position.z,
                );
            }
        }
        for (const [mesh, speed] of this.spins) {
            if (mesh.geometry instanceof THREE.RingGeometry) {
                mesh.rotation.z += speed * dt;
            } else {
                mesh.rotation.y += speed * dt;
            }
        }
        // Ships point down the leg they are flying: a heading read slightly
        // ahead on the resolver, so a docked ship still faces its next stop.
        const ahead = new THREE.Vector3();
        for (const ship of this.ships) {
            const [x, y, z] = this.resolve(ship.id, this.elapsed + 0.6);
            ahead.set(x, y, z).sub(ship.mesh.position);
            if (ahead.lengthSq() > 1e-10) {
                ship.mesh.lookAt(ahead.add(ship.mesh.position));
            }
        }
        this.layoutLabels();
        for (const disc of this.discs) {
            disc.rotation.y += 0.02 * dt;
        }
        for (const halo of this.halos) {
            halo.sprite.scale.setScalar(
                halo.base * (1 + 0.05 * Math.sin(this.elapsed * 1.3 + halo.seed)),
            );
        }
        for (const material of this.sunMaterials) {
            material.uniforms.uTime.value = this.elapsed;
        }
        for (const material of this.portalMaterials) {
            material.uniforms.uTime.value = this.elapsed;
        }
        // Anamorphic streaks live near the camera and twinkle; far stars
        // stay clean glows.
        for (const streak of this.sunStreaks) {
            const d = this.camera.position.distanceTo(streak.mesh.position);
            const near = Math.min(Math.max((2.6 - d) / 2.0, 0), 1);
            const twinkle = 0.85 + 0.15 * Math.sin(this.elapsed * 1.6 + streak.seed);
            streak.material.opacity = streak.base * near * twinkle;
            streak.material.visible = streak.material.opacity > 0.01;
        }
        // Citation bonds: a selected planet's light-lines to the suns it
        // cites beyond its home track both endpoints live.
        for (const bond of this.bonds) {
            const from = this.meshById.get(bond.fromId);
            const to = this.meshById.get(bond.toId);
            if (from && to) {
                const positions = bond.geometry.getAttribute('position') as THREE.BufferAttribute;
                positions.setXYZ(0, from.position.x, from.position.y, from.position.z);
                positions.setXYZ(1, to.position.x, to.position.y, to.position.z);
                positions.needsUpdate = true;
            }
        }
        // Each world keeps facing its own sun as it orbits (and as its sun
        // re-seats during a filter reflow).
        for (const shade of this.planetShades) {
            const sunMesh = shade.sunId ? this.meshById.get(shade.sunId) : undefined;
            (shade.material.uniforms.uSunDir.value as THREE.Vector3)
                .copy(sunMesh ? sunMesh.position : shade.sunPos)
                .sub(shade.mesh.position)
                .normalize();
        }
        // Filter transitions: bodies scale away and back, never popping.
        for (let i = this.filterTweens.length - 1; i >= 0; i -= 1) {
            const tween = this.filterTweens[i];
            const raw = Math.min((this.elapsed - tween.start) / 0.35, 1);
            const eased = 1 - (1 - raw) ** 3;
            const scale = tween.from + (tween.to - tween.from) * eased;
            tween.mesh.scale.setScalar(Math.max(scale, 0.001));
            if (raw >= 1) {
                if (tween.to < 0.5) {
                    tween.mesh.visible = false;
                    tween.mesh.scale.setScalar(1);
                }
                this.filterTweens.splice(i, 1);
            }
        }
        // Bulge glows are far-view dressing: inside a galaxy they would wash
        // the whole sky, so they fade with camera proximity.
        for (const bulge of this.bulges) {
            const d = this.camera.position.distanceTo(bulge.sprite.position);
            const t = Math.min(Math.max((d - 1.1) / 1.5, 0), 1);
            bulge.sprite.material.opacity = bulge.base * t;
        }
        // Camera context LATCHES: entering a galaxy's sphere sets or switches
        // it; leaving never clears it (a zoom-out keeps the focus working).
        if (this.elapsed - this.contextCheckAt > 0.25) {
            this.contextCheckAt = this.elapsed;
            let nearest: string | null = null;
            let best = Infinity;
            for (const galaxy of this.model.galaxies) {
                const d =
                    Math.hypot(
                        this.camera.position.x - galaxy.center[0],
                        this.camera.position.y - galaxy.center[1],
                        this.camera.position.z - galaxy.center[2],
                    ) /
                    (galaxy.radius * 2.2);
                if (d < 1 && d < best) {
                    best = d;
                    nearest = galaxy.name;
                }
            }
            if (nearest !== null) {
                this.setGalaxyContext(nearest);
            }
        }
        this.updateFollow();
        this.updateTween();

        if (this.renderer.xr.isPresenting) {
            this.renderer.render(this.scene, this.camera);
        } else {
            this.controls.update();
            this.composer.render();
        }
    };

    private startTween(position: THREE.Vector3, target: THREE.Vector3, duration: number): void {
        this.tween = {
            fromPosition: this.camera.position.clone(),
            toPosition: position,
            fromTarget: this.controls.target.clone(),
            toTarget: target,
            offset: position.clone().sub(target),
            start: this.elapsed,
            duration,
        };
    }

    /** Keep the camera glued to an orbiting subject: retarget the tween while
     *  in flight, and after arrival translate camera and target together. */
    private updateFollow(): void {
        if (!this.followId || this.renderer.xr.isPresenting) {
            return;
        }
        // The mesh already carries orbit and reflow offsets this frame.
        const followMesh = this.meshById.get(this.followId);
        const position = followMesh
            ? followMesh.position.clone()
            : new THREE.Vector3(...this.resolve(this.followId, this.elapsed));
        if (this.tween) {
            this.tween.toTarget.copy(position);
            this.tween.toPosition.copy(position).add(this.tween.offset);
            return;
        }
        const delta = position.clone().sub(this.controls.target);
        this.controls.target.copy(position);
        this.camera.position.add(delta);
        // The reading panel rides along, or a long read leaves it behind.
        this.panel?.position.add(delta);
    }

    private updateTween(): void {
        if (!this.tween || this.renderer.xr.isPresenting) {
            return;
        }
        const raw = (this.elapsed - this.tween.start) / this.tween.duration;
        const clamped = Math.min(Math.max(raw, 0), 1);
        const eased = clamped < 0.5 ? 4 * clamped ** 3 : 1 - (-2 * clamped + 2) ** 3 / 2;
        this.camera.position.lerpVectors(this.tween.fromPosition, this.tween.toPosition, eased);
        this.controls.target.lerpVectors(this.tween.fromTarget, this.tween.toTarget, eased);
        if (clamped >= 1) {
            this.tween = null;
        }
    }

    /** The current reflow displacement affecting a body (its own, if a sun;
     *  its governing sun's otherwise). */
    private liveOffsetOf(body: SceneBody): THREE.Vector3 | null {
        const sunId = body.kind === 'sun' ? body.id : (this.sunOfBody.get(body.id) ?? null);
        return sunId ? (this.sunOffsets.get(sunId)?.current ?? null) : null;
    }

    private flyTo(body: SceneBody): void {
        this.followId = body.orbit || body.kind === 'moon' ? body.id : null;
        const [x, y, z] = this.resolve(body.id, this.elapsed);
        const offset = this.liveOffsetOf(body);
        const target = new THREE.Vector3(x, y, z);
        if (offset) {
            target.add(offset);
        }
        const distance =
            body.kind === 'hub'
                ? 1.3
                : body.kind === 'galaxy' || body.kind === 'nebula'
                  ? body.size * 2.6
                  : body.kind === 'sun'
                    ? Math.max(body.size * 4.5, 0.3)
                    : body.kind === 'door'
                      ? body.size * 7 + 0.06
                      : body.kind === 'agent'
                        ? body.size * 8 + 0.04
                        : body.kind === 'moon'
                          ? body.size * 5 + 0.02
                          : body.size * 4 + 0.03;
        const direction = this.camera.position.clone().sub(target).normalize();
        if (direction.lengthSq() < 0.001) {
            direction.set(0, 0.25, 1).normalize();
        }
        // Arrive from slightly above the disc plane: bodies frame against
        // space, not through the crowded in-plane particle soup.
        direction.y += 0.55;
        direction.normalize();
        this.startTween(target.clone().addScaledVector(direction, distance), target, 1.2);
    }

    private onResize(): void {
        const width = this.container.clientWidth;
        const height = Math.max(this.container.clientHeight, 1);
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height, false);
        this.composer.setSize(width, height);
    }

    private readonly onPointerMove = (event: PointerEvent): void => {
        const bounds = this.renderer.domElement.getBoundingClientRect();
        this.pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
        this.pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
        this.raycaster.setFromCamera(this.pointer, this.camera);
        const hit =
            this.raycaster.intersectObjects(this.pickables, false).find((i) => i.object.visible)
                ?.object ?? null;
        if (hit !== this.hovered) {
            if (this.hovered) {
                const label = this.labels.get(this.hovered);
                if (label) {
                    label.visible = false;
                }
            }
            this.hovered = hit;
            if (hit) {
                const label = this.labels.get(hit);
                if (label) {
                    label.visible = true;
                }
            }
            this.container.style.cursor = hit ? 'pointer' : 'default';
        }
    };

    private readonly onClick = (): void => {
        this.clicks += 1;
        this.raycaster.setFromCamera(this.pointer, this.camera);
        this.handleRayHit();
    };

    private readonly onDoubleClick = (): void => {
        this.raycaster.setFromCamera(this.pointer, this.camera);
        const hit = this.raycaster
            .intersectObjects(this.pickables, false)
            .find((i) => i.object.visible);
        if (!hit) {
            this.closePanel();
            this.flyHome();
        }
    };

    private readonly onControllerSelect = (event: { target: THREE.Object3D }): void => {
        const controller = event.target;
        const origin = new THREE.Vector3();
        const direction = new THREE.Vector3(0, 0, -1);
        controller.getWorldPosition(origin);
        direction.applyQuaternion(controller.getWorldQuaternion(new THREE.Quaternion()));
        this.raycaster.set(origin, direction);
        this.handleRayHit();
    };

    private handleRayHit(): void {
        // The panel consumes its hits: buttons act, links travel, and no
        // click ever selects a body through the glass.
        if (this.panel && this.panelState) {
            const panelHit = this.raycaster.intersectObjects(
                [this.panel, ...this.panelButtons],
                false,
            )[0];
            if (panelHit) {
                const action = panelHit.object.name;
                if (action === 'panel-close') {
                    this.closePanel();
                } else if (action === 'panel-up' || action === 'panel-down') {
                    this.scrollPanel(action === 'panel-down' ? 8 : -8);
                } else if (panelHit.uv) {
                    const x = panelHit.uv.x * PANEL_CANVAS_W;
                    const y = (1 - panelHit.uv.y) * PANEL_CANVAS_H;
                    const link = this.panelLinks.find(
                        (r) => x >= r.x0 && x <= r.x1 && y >= r.y0 && y <= r.y1,
                    );
                    if (link) {
                        this.select(link.target);
                    }
                }
                return;
            }
        }
        const hit = this.raycaster
            .intersectObjects(this.pickables, false)
            .find((i) => i.object.visible)?.object;
        if (!hit) {
            return;
        }
        const body = this.byMesh.get(hit);
        if (body) {
            if (body.galaxy) {
                this.setGalaxyContext(body.galaxy);
            }
            this.lastSelected = body.id;
            this.flyTo(body);
            this.onSelect(body);
        }
    }

    private scrollPanel(delta: number): void {
        if (!this.panelState) {
            return;
        }
        const max = Math.max(0, this.panelState.lines.length - this.panelVisible);
        const next = Math.min(Math.max(this.panelState.scroll + delta, 0), max);
        if (next !== this.panelState.scroll) {
            this.panelState.scroll = next;
            this.renderPanel();
        }
    }

    private renderPanel(): void {
        if (!this.panelState) {
            return;
        }
        const texture = this.drawPanel(this.panelState);
        if (this.panel) {
            const material = this.panel.material as THREE.MeshBasicMaterial;
            material.map?.dispose();
            material.map = texture;
            material.needsUpdate = true;
            return;
        }
        const material = new THREE.MeshBasicMaterial({
            map: texture,
            toneMapped: false,
            transparent: true,
        });
        this.panel = new THREE.Mesh(new THREE.PlaneGeometry(PANEL_WIDTH, PANEL_HEIGHT), material);
        this.placePanelInFront();
        this.scene.add(this.panel);

        const mkButton = (name: string, x: number, color: string): THREE.Mesh => {
            const button = new THREE.Mesh(
                new THREE.CircleGeometry(0.035, 24),
                new THREE.MeshBasicMaterial({ color, toneMapped: false }),
            );
            button.name = name;
            button.position.set(x, -PANEL_HEIGHT / 2 - 0.06, 0);
            this.panel?.add(button);
            return button;
        };
        this.panelButtons = [
            mkButton('panel-up', -0.12, '#475569'),
            mkButton('panel-down', 0.12, '#475569'),
            mkButton('panel-close', PANEL_WIDTH / 2 - 0.04, '#b91c1c'),
        ];
    }

    /** Paint the current panel state: styled lines from the layout engine,
     *  travel-links overdrawn in accent with hit rects, and a scrollbar. */
    private drawPanel(state: PanelState): THREE.CanvasTexture {
        const canvas = document.createElement('canvas');
        canvas.width = PANEL_CANVAS_W;
        canvas.height = PANEL_CANVAS_H;
        const ctx = canvas.getContext('2d');
        this.panelLinks = [];
        if (!ctx) {
            return new THREE.CanvasTexture(canvas);
        }
        const specs = panelSpecs(state.accent);

        ctx.fillStyle = '#0b1220f2';
        ctx.beginPath();
        ctx.roundRect(0, 0, canvas.width, canvas.height, 18);
        ctx.fill();
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.fillStyle = state.accent;
        ctx.fillRect(0, 18, 8, canvas.height - 36);

        ctx.textBaseline = 'alphabetic';
        ctx.fillStyle = '#f8fafc';
        ctx.font = '800 40px system-ui, sans-serif';
        ctx.fillText(state.title, 48, 66);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '22px system-ui, sans-serif';
        ctx.fillText(state.meta, 48, 102);
        ctx.strokeStyle = '#1e293b';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(48, 124);
        ctx.lineTo(canvas.width - 48, 124);
        ctx.stroke();

        const top = 164;
        const bottom = canvas.height - 60;
        let y = top;
        let index = state.scroll;
        while (index < state.lines.length) {
            const line = state.lines[index];
            const spec = specs[line.style];
            if (y + spec.lineHeight > bottom) {
                break;
            }
            y += spec.lineHeight;
            index += 1;
            if (line.style === 'gap') {
                continue;
            }
            let x = 48 + line.indent * 22;
            ctx.font = spec.font;
            if (line.style === 'code') {
                ctx.fillStyle = '#1e293b';
                ctx.fillRect(40, y - spec.lineHeight + 6, canvas.width - 104, spec.lineHeight);
            }
            if (line.style === 'bullet') {
                ctx.fillStyle = state.accent;
                ctx.fillText('•', x, y);
                x += 24;
            }
            if (line.style === 'quote') {
                ctx.fillStyle = `${state.accent}99`;
                ctx.fillRect(44, y - spec.lineHeight + 8, 4, spec.lineHeight - 6);
                x += 18;
            }
            ctx.fillStyle = spec.fill;
            ctx.fillText(line.text, x, y);
            for (const link of line.links) {
                const prefix = line.text.slice(0, link.start);
                const label = line.text.slice(link.start, link.end);
                const lx = x + ctx.measureText(prefix).width;
                const lw = ctx.measureText(label).width;
                ctx.fillStyle = state.accent;
                ctx.fillText(label, lx, y);
                ctx.fillRect(lx, y + 5, lw, 2);
                this.panelLinks.push({
                    x0: lx - 4,
                    y0: y - spec.lineHeight,
                    x1: lx + lw + 4,
                    y1: y + 10,
                    target: link.target,
                });
            }
        }
        this.panelVisible = Math.max(index - state.scroll, 1);

        if (state.lines.length > this.panelVisible) {
            const trackTop = top - 20;
            const trackH = bottom - trackTop;
            ctx.fillStyle = '#1e293b';
            ctx.fillRect(canvas.width - 26, trackTop, 6, trackH);
            const thumbH = Math.max((this.panelVisible / state.lines.length) * trackH, 34);
            const thumbTop =
                trackTop +
                (state.scroll / Math.max(state.lines.length - this.panelVisible, 1)) *
                    (trackH - thumbH);
            ctx.fillStyle = `${state.accent}aa`;
            ctx.fillRect(canvas.width - 26, thumbTop, 6, thumbH);
        }

        ctx.fillStyle = '#64748b';
        ctx.font = '19px system-ui, sans-serif';
        ctx.fillText('o up | o down | o close  ·  tap a link to travel', 48, canvas.height - 26);
        const range = `${state.scroll + 1}-${Math.min(state.scroll + this.panelVisible, state.lines.length)} / ${state.lines.length}`;
        ctx.fillText(range, canvas.width - 48 - ctx.measureText(range).width, canvas.height - 26);

        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        return texture;
    }

    private placePanelInFront(): void {
        if (!this.panel) {
            return;
        }
        if (this.renderer.xr.isPresenting) {
            const xrCamera = this.renderer.xr.getCamera();
            const direction = new THREE.Vector3();
            xrCamera.getWorldDirection(direction);
            const origin = new THREE.Vector3();
            xrCamera.getWorldPosition(origin);
            this.panel.position.copy(origin).addScaledVector(direction, 1.25);
            this.panel.lookAt(origin);
            return;
        }
        // A fly-to may be in flight: pose the panel where the camera will BE,
        // beside the destination's line of sight, so arrival frames both.
        const origin = this.tween ? this.tween.toPosition.clone() : this.camera.position.clone();
        const focus = this.tween ? this.tween.toTarget.clone() : this.controls.target.clone();
        const forward = focus.clone().sub(origin).normalize();
        const side = forward
            .clone()
            .cross(new THREE.Vector3(0, 1, 0))
            .normalize();
        this.panel.position.copy(origin).addScaledVector(forward, 1.15).addScaledVector(side, 0.55);
        this.panel.lookAt(origin);
    }
}

/** A soft radial glow, tinted; the corona and nebula workhorse. */
function radialGlowTexture(color: string, innerStop: number): THREE.CanvasTexture {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');
    if (ctx) {
        const tint = new THREE.Color(color);
        const gradient = ctx.createRadialGradient(128, 128, 8, 128, 128, 128);
        const rgb = `${Math.round(tint.r * 255)}, ${Math.round(tint.g * 255)}, ${Math.round(tint.b * 255)}`;
        gradient.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
        gradient.addColorStop(innerStop, `rgba(${rgb}, 0.55)`);
        gradient.addColorStop(1, `rgba(${rgb}, 0)`);
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 256, 256);
        // Dither the falloff so additive stacking never bands.
        const rand = seededRandom(0xd17);
        const img = ctx.getImageData(0, 0, 256, 256);
        for (let i = 3; i < img.data.length; i += 4) {
            img.data[i] = Math.min(Math.max(img.data[i] + (rand() - 0.5) * 5, 0), 255);
        }
        ctx.putImageData(img, 0, 0);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
}

function makeTextSprite(text: string, fontPx: number, color: string): THREE.Sprite {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const font = `600 ${fontPx * 2}px system-ui, sans-serif`;
    if (ctx) {
        ctx.font = font;
        canvas.width = Math.ceil(ctx.measureText(text).width) + 24;
        canvas.height = fontPx * 2 + 20;
        ctx.font = font;
        ctx.fillStyle = color;
        ctx.textBaseline = 'middle';
        ctx.shadowColor = 'rgba(2, 6, 23, 0.9)';
        ctx.shadowBlur = 8;
        ctx.fillText(text, 12, canvas.height / 2);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: texture, transparent: true, toneMapped: false }),
    );
    const scale = 0.0016;
    sprite.scale.set(canvas.width * scale, canvas.height * scale, 1);
    sprite.userData = { width: canvas.width, height: canvas.height };
    return sprite;
}

function disposeObject(root: THREE.Object3D): void {
    root.traverse((child) => {
        const mesh = child as THREE.Mesh;
        mesh.geometry?.dispose();
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const material of materials) {
            if (!material) {
                continue;
            }
            for (const value of Object.values(material)) {
                if ((value as THREE.Texture)?.isTexture) {
                    (value as THREE.Texture).dispose();
                }
            }
            material.dispose();
        }
    });
}
