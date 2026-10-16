import * as THREE from "three";

/** Entire scene is original procedural geometry. No models, HDRIs or remote textures. */
export type PerfumeSpatialController = {
  setExplored(value: boolean, immediate?: boolean): void;
  setPointer(x: number, y: number): void;
  setVisible(value: boolean): void;
  dispose(): void;
};

type Options = { reducedMotion: boolean; isVisible?(): boolean; onContextLost(): void };

function bevelledBody(width: number, height: number, depth: number, bevel: number) {
  const segments = 96;
  const positions: number[] = [];
  const indices: number[] = [];
  const half = height / 2;
  const profiles = [
    [-half, .87], [-half + bevel * .18, .92], [-half + bevel * .55, .98],
    [-half + bevel, 1], [-half + bevel * 1.5, 1],
    [half - bevel * 1.8, 1], [half - bevel, .99],
    [half - bevel * .55, .96], [half - bevel * .18, .9], [half, .85],
  ];
  for (const [y, size] of profiles) {
    for (let i = 0; i <= segments; i++) {
      const theta = i / segments * Math.PI * 2;
      const cos = Math.cos(theta), sin = Math.sin(theta);
      const exponent = .48;
      positions.push(Math.sign(cos) * Math.pow(Math.abs(cos), exponent) * width / 2 * size,
        y, Math.sign(sin) * Math.pow(Math.abs(sin), exponent) * depth / 2 * size);
    }
  }
  for (let ring = 0; ring < profiles.length - 1; ring++) {
    for (let i = 0; i < segments; i++) {
      const a = ring * (segments + 1) + i, b = a + segments + 1;
      indices.push(a, b, a + 1, a + 1, b, b + 1);
    }
  }
  const bottomCenter = positions.length / 3;
  positions.push(0, -half, 0);
  const topCenter = positions.length / 3;
  positions.push(0, half, 0);
  const top = (profiles.length - 1) * (segments + 1);
  for (let i = 0; i < segments; i++) indices.push(bottomCenter, i, i + 1, topCenter, top + i + 1, top + i);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function superellipsePlate(width: number, depth: number, exponent = .48) {
  const shape = new THREE.Shape();
  const segments = 96;
  for (let i = 0; i <= segments; i++) {
    const theta = i / segments * Math.PI * 2;
    const cos = Math.cos(theta), sin = Math.sin(theta);
    const x = Math.sign(cos) * Math.pow(Math.abs(cos), exponent) * width / 2;
    const y = Math.sign(sin) * Math.pow(Math.abs(sin), exponent) * depth / 2;
    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  }
  shape.closePath();
  const geometry = new THREE.ShapeGeometry(shape, 12);
  geometry.rotateX(-Math.PI / 2);
  return geometry;
}

function mistTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const context = canvas.getContext("2d")!;
  const gradient = context.createRadialGradient(32, 32, 0, 32, 32, 31);
  gradient.addColorStop(0, "rgba(255,252,244,.82)");
  gradient.addColorStop(.28, "rgba(255,247,229,.38)");
  gradient.addColorStop(.7, "rgba(255,245,224,.09)");
  gradient.addColorStop(1, "rgba(255,245,224,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 64, 64);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function labelTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 768;
  canvas.height = 640;
  const context = canvas.getContext("2d")!;
  context.fillStyle = "#eee7d9";
  context.fillRect(0, 0, 768, 640);
  context.strokeStyle = "#a89a7d";
  context.lineWidth = 2;
  context.strokeRect(30, 30, 708, 580);
  context.textAlign = "center";
  context.fillStyle = "#453e32";
  context.font = "38px Arial";
  context.letterSpacing = "12px";
  context.fillText("D U F Y N D", 384, 137);
  context.font = "italic 184px Georgia";
  context.letterSpacing = "0px";
  context.fillText("n° 01", 384, 382);
  context.fillStyle = "#81745e";
  context.fillRect(321, 436, 126, 2);
  context.font = "20px Arial";
  context.fillText("É T U D E   D E   P A R F U M", 384, 518);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

function shadowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  const gradient = ctx.createRadialGradient(128, 128, 8, 128, 128, 124);
  gradient.addColorStop(0, "rgba(49,35,20,.35)");
  gradient.addColorStop(.35, "rgba(65,45,26,.20)");
  gradient.addColorStop(.67, "rgba(89,63,36,.07)");
  gradient.addColorStop(1, "rgba(89,63,36,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(canvas);
}

export async function createPerfumeSpatialRenderer(host: HTMLDivElement, options: Options): Promise<PerfumeSpatialController> {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
  let didDispose = false;
  try {
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, window.innerWidth < 768 ? 1.35 : 1.65));
  renderer.setClearColor(0xeee8de, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .94;
  renderer.domElement.setAttribute("aria-hidden", "true");
  renderer.domElement.setAttribute("data-spatial-webgl", "true");
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = null;
  const camera = new THREE.PerspectiveCamera(30, 1, .1, 60);
  camera.position.set(4.35, 3.06, 7.48);
  camera.lookAt(0, 1.74, 0);

  // A small authored studio environment: long reflected softboxes define the glass.
  const studio = new THREE.Scene();
  studio.background = new THREE.Color("#171512");
  const room = new THREE.Mesh(new THREE.BoxGeometry(24, 18, 24), new THREE.MeshBasicMaterial({ color: 0x39352e, side: THREE.BackSide }));
  studio.add(room);
  const panel = (width: number, height: number, position: [number, number, number], color: number, intensity: number) => {
    const material = new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide });
    material.color.multiplyScalar(intensity);
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), material);
    mesh.position.set(...position);
    mesh.lookAt(0, 1.8, 0);
    studio.add(mesh);
  };
  panel(1.15, 9.5, [-4.4, 2.3, 6.8], 0xfff8e8, 9);
  panel(.36, 8.5, [4.25, 2.25, 5.7], 0xf8fbff, 7.5);
  panel(5.5, 3.4, [-.3, 8.2, .2], 0xfff3dd, 2.6);
  panel(2.2, 7.5, [1.1, 2.6, -6], 0xffc66f, 2.0);
  panel(1.0, 8.5, [2.8, 2.0, 6.5], 0x25231f, 1.1);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const environment = pmrem.fromScene(studio, .035, .1, 30);
  scene.environment = environment.texture;
  scene.environmentIntensity = .94;
  studio.traverse((object) => {
    if (object instanceof THREE.Mesh) {
      object.geometry.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => material.dispose());
    }
  });
  pmrem.dispose();

  const backdropCanvas = document.createElement("canvas");
  backdropCanvas.width = 1024;
  backdropCanvas.height = 1024;
  const backdropContext = backdropCanvas.getContext("2d")!;
  backdropContext.clearRect(0, 0, 1024, 1024);
  const studioGlow = backdropContext.createRadialGradient(450, 610, 24, 450, 610, 470);
  studioGlow.addColorStop(0, "rgba(255,253,246,.92)");
  studioGlow.addColorStop(.42, "rgba(246,240,227,.52)");
  studioGlow.addColorStop(.72, "rgba(231,218,199,.16)");
  studioGlow.addColorStop(1, "rgba(231,218,199,0)");
  backdropContext.fillStyle = studioGlow;
  backdropContext.fillRect(0, 0, 1024, 1024);
  const studioShade = backdropContext.createLinearGradient(360, 170, 920, 700);
  studioShade.addColorStop(0, "rgba(74,55,36,0)");
  studioShade.addColorStop(.28, "rgba(74,55,36,0)");
  studioShade.addColorStop(.48, "rgba(74,55,36,.16)");
  studioShade.addColorStop(.61, "rgba(58,42,27,.11)");
  studioShade.addColorStop(.78, "rgba(58,42,27,.035)");
  studioShade.addColorStop(1, "rgba(58,42,27,0)");
  backdropContext.fillStyle = studioShade;
  backdropContext.fillRect(0, 0, 1024, 1024);
  const backdropMap = new THREE.CanvasTexture(backdropCanvas);
  backdropMap.colorSpace = THREE.SRGBColorSpace;
  const backdrop = new THREE.Mesh(new THREE.PlaneGeometry(10.2, 10.2), new THREE.MeshBasicMaterial({
    map: backdropMap, transparent: true, opacity: .96, depthWrite: false, toneMapped: false,
  }));
  backdrop.position.set(-1.4, 1.7, -3.6);
  backdrop.quaternion.copy(camera.quaternion);
  scene.add(backdrop);

  const hemisphere = new THREE.HemisphereLight(0xfffcf3, 0x71604b, .6);
  scene.add(hemisphere);
  const key = new THREE.DirectionalLight(0xfff9eb, 1.5);
  key.position.set(-5, 6, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xffffff, 1);
  rim.position.set(3, 4, -4);
  scene.add(rim);

  const assembly = new THREE.Group();
  assembly.rotation.set(-.02, -.12, -.035);
  assembly.position.y = -.11;
  scene.add(assembly);

  const glassMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, roughness: .003, metalness: 0, transmission: 1,
    thickness: .075, ior: 1.52, envMapIntensity: 2.75, dispersion: .006,
    attenuationColor: new THREE.Color(0xffffff), attenuationDistance: 140,
    clearcoat: .18, clearcoatRoughness: .006,
  });
  const refractionType = renderer.extensions.has("EXT_color_buffer_half_float") || renderer.extensions.has("EXT_color_buffer_float")
    ? THREE.HalfFloatType : THREE.UnsignedByteType;
  // Physical transmission uses bicubic mip sampling: the target must supply all LODs.
  const refractionTarget = new THREE.WebGLRenderTarget(1, 1, {
    type: refractionType, samples: 2, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter,
  });
  glassMaterial.onBeforeCompile = (shader) => {
    shader.uniforms.studioRefractionMap = { value: refractionTarget.texture };
    shader.fragmentShader = shader.fragmentShader.replace("#include <transmission_pars_fragment>", THREE.ShaderChunk.transmission_pars_fragment.replaceAll("transmissionSamplerMap", "studioRefractionMap"));
  };
  const glass = new THREE.Mesh(bevelledBody(2.2, 2.45, 1.14, .12), glassMaterial);
  glass.position.set(0, 1.42, 0);
  glass.renderOrder = 4;
  assembly.add(glass);

  // A restrained Fresnel shell draws only grazing-angle highlights: edge definition
  // without adding another transmissive layer to Three's screen-space refraction.
  const glassEdgeMaterial = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      varying vec3 vStudyNormal;
      varying vec3 vStudyView;
      void main() {
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        vStudyNormal = normalize(normalMatrix * normal);
        vStudyView = normalize(-mvPosition.xyz);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying vec3 vStudyNormal;
      varying vec3 vStudyView;
      void main() {
        float rim = pow(1.0 - clamp(abs(dot(normalize(vStudyNormal), normalize(vStudyView))), 0.0, 1.0), 2.35);
        float alpha = rim * 0.145;
        gl_FragColor = vec4(vec3(1.0, 0.985, 0.95) * (0.72 + rim * 0.55), alpha);
      }
    `,
  });
  const glassEdge = new THREE.Mesh(glass.geometry, glassEdgeMaterial);
  glassEdge.position.copy(glass.position);
  glassEdge.scale.set(1.003, 1.002, 1.008);
  glassEdge.renderOrder = 7;
  assembly.add(glassEdge);

  // A separate inner wall makes the vessel read as a hollow glass object rather than a milky solid.
  const innerGlassMaterial = new THREE.MeshStandardMaterial({
    color: 0xfffdf7, roughness: .08, metalness: 0,
    transparent: true, opacity: .026, depthWrite: false, side: THREE.BackSide,
    envMapIntensity: 1.45,
  });
  const innerGlass = new THREE.Mesh(bevelledBody(2.00, 2.24, .94, .095), innerGlassMaterial);
  innerGlass.position.set(0, 1.43, 0);
  innerGlass.renderOrder = 3;
  assembly.add(innerGlass);

  // The amber reservoir uses volume absorption and is captured before the outer-glass refraction pass.
  const liquidMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xffd08a, roughness: .015, metalness: 0, transmission: .94,
    thickness: .18, ior: 1.335, attenuationColor: new THREE.Color(0xc87824), attenuationDistance: 2.8,
    clearcoat: .05, clearcoatRoughness: .01, envMapIntensity: 1.25,
  });
  liquidMaterial.onBeforeCompile = (shader) => {
    shader.vertexShader = "varying vec3 vStudyPosition;\n" + shader.vertexShader.replace("#include <begin_vertex>", "#include <begin_vertex>\n vStudyPosition = position;");
    shader.fragmentShader = "varying vec3 vStudyPosition;\n" + shader.fragmentShader.replace("#include <transmission_fragment>", THREE.ShaderChunk.transmission_fragment.replace("material.thickness = thickness;", "material.thickness = thickness * (0.70 + 0.45 * pow(abs(vStudyPosition.x) / 0.93, 3.0));"));
  };
  const liquid = new THREE.Mesh(bevelledBody(1.85, 1.44, .78, .075), liquidMaterial);
  liquid.position.set(0, 1.255, 0);
  liquid.renderOrder = 2;
  assembly.add(liquid);

  // The flat surface/meniscus is intentionally separate from the rounded reservoir edge.
  const meniscusMaterial = new THREE.MeshStandardMaterial({
    color: 0xc9812d, roughness: .06, metalness: 0, envMapIntensity: 1.35,
    transparent: true, opacity: .20, depthWrite: false, side: THREE.DoubleSide,
  });
  const meniscus = new THREE.Mesh(superellipsePlate(1.72, .68), meniscusMaterial);
  meniscus.position.set(0, 1.982, 0);
  meniscus.renderOrder = 5;
  assembly.add(meniscus);

  const baseMaterial = new THREE.MeshStandardMaterial({
    color: 0xffffff, roughness: .08, metalness: 0, envMapIntensity: 1.6,
    transparent: true, opacity: .035, depthWrite: false, side: THREE.DoubleSide,
  });
  const base = new THREE.Mesh(bevelledBody(2.03, .13, 1.0, .035), baseMaterial);
  base.position.set(0, .245, 0);
  base.renderOrder = 3;
  assembly.add(base);

  const neck = new THREE.Mesh(new THREE.CylinderGeometry(.31, .4, .38, 48), glassMaterial);
  neck.position.y = 2.7;
  assembly.add(neck);

  const metal = new THREE.MeshStandardMaterial({ color: 0xe1d9c8, metalness: 1, roughness: .3, envMapIntensity: 1.0 });
  const metalEdge = new THREE.MeshStandardMaterial({ color: 0xe7d6b1, metalness: 1, roughness: .15 });
  const darkMetal = new THREE.MeshStandardMaterial({ color: 0x53534c, metalness: 1, roughness: .28 });
  const atomizer = new THREE.Group();
  atomizer.position.y = 2.77;
  const collar = new THREE.Mesh(new THREE.CylinderGeometry(.36, .36, .2, 64), metal);
  atomizer.add(collar);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(.355, .022, 6, 64), metalEdge);
  ring.rotation.x = Math.PI / 2;
  ring.position.y = -.06;
  atomizer.add(ring);
  const sprayer = new THREE.Mesh(new THREE.CylinderGeometry(.19, .19, .34, 48), metalEdge);
  sprayer.position.y = .23;
  atomizer.add(sprayer);
  const aperture = new THREE.Mesh(new THREE.CylinderGeometry(.045, .045, .02, 24), darkMetal);
  aperture.rotation.x = Math.PI / 2;
  aperture.position.set(0, .27, .195);
  atomizer.add(aperture);
  const tube = new THREE.Mesh(new THREE.CylinderGeometry(.018, .018, 1.87, 8), new THREE.MeshStandardMaterial({ color: 0xe5cf98, transparent: true, opacity: .5, roughness: .2 }));
  tube.position.y = -.99;
  atomizer.add(tube);
  assembly.add(atomizer);

  const cap = new THREE.Group();
  cap.position.y = 3.13;
  const capBody = new THREE.Mesh(new THREE.CylinderGeometry(.48, .51, .69, 64, 1), metal);
  cap.add(capBody);
  const capTop = new THREE.Mesh(new THREE.CylinderGeometry(.456, .456, .025, 64), darkMetal);
  capTop.position.y = .354;
  cap.add(capTop);
  const topRim = new THREE.Mesh(new THREE.TorusGeometry(.455, .017, 6, 64), metalEdge);
  topRim.rotation.x = Math.PI / 2;
  topRim.position.y = .355;
  cap.add(topRim);
  // Fine machined grooves are geometry, visible as restrained highlights rather than a texture.
  for (let index = 0; index < 4; index += 1) {
    const groove = new THREE.Mesh(new THREE.TorusGeometry(.503 - index * .001, .008, 4, 64), darkMetal);
    groove.rotation.x = Math.PI / 2;
    groove.position.y = -.27 + index * .022;
    cap.add(groove);
  }
  assembly.add(cap);

  const labelMap = labelTexture();
  const label = new THREE.Mesh(new THREE.PlaneGeometry(1.04, .87), new THREE.MeshStandardMaterial({
    map: labelMap, color: 0xffffff, roughness: .88, metalness: 0, transparent: true, depthWrite: false, depthTest: false,
  }));
  label.position.set(0, 1.45, .59);
  label.renderOrder = 10;
  assembly.add(label);

  const shadowMap = shadowTexture();
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(5.5, 3.3), new THREE.MeshBasicMaterial({
    map: shadowMap, transparent: true, depthWrite: false, toneMapped: false,
  }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.set(.05, .055, .0);
  scene.add(shadow);

  // A short, deterministic atomizer mist appears only during the opening gesture.
  const mistPositions: number[] = [];
  for (let index = 0; index < 58; index += 1) {
    const t = index / 57;
    const phase = index * 2.399963;
    mistPositions.push(
      .03 + t * 1.42 + Math.sin(phase) * t * .10,
      3.16 + t * .18 + Math.cos(phase * 1.7) * t * .11,
      .22 + t * .72 + Math.sin(phase * .8) * t * .06,
    );
  }
  const mistGeometry = new THREE.BufferGeometry();
  mistGeometry.setAttribute("position", new THREE.Float32BufferAttribute(mistPositions, 3));
  const mistMap = mistTexture();
  const mistMaterial = new THREE.PointsMaterial({
    map: mistMap, color: 0xfff3db, size: .085, sizeAttenuation: true,
    transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const mist = new THREE.Points(mistGeometry, mistMaterial);
  mist.frustumCulled = false;
  mist.renderOrder = 20;
  assembly.add(mist);
  const sprayLight = new THREE.PointLight(0xffd9a0, 0, 2.4, 2);
  sprayLight.position.set(.5, 3.25, .55);
  assembly.add(sprayLight);

  let disposed = false;
  let initializing = true;
  let visible = options.isVisible?.() ?? true;
  let frame = 0;
  let renderCount = 0;
  let framingFov = 30;
  let explored = 0;
  let exploreTarget = 0;
  let startProgress = 0;
  let transitionStart = 0;
  let rotating = false;
  let openingMotion = false;
  const rotation = { x: -.02, y: -.12 };
  const target = { ...rotation };

  function updateParts(progress: number) {
    cap.position.set(.34 * progress, 3.13 + progress * 1.04, .10 * progress);
    cap.rotation.z = progress * -.115;
    cap.rotation.y = progress * .10;
    atomizer.position.set(-.10 * progress, 2.77 + progress * .46, .07 * progress);
    atomizer.rotation.z = progress * .045;
    const shellShift = -.095 * progress;
    const liquidShift = .085 * progress;
    glass.position.x = shellShift;
    glass.rotation.y = progress * -.025;
    innerGlass.position.x = shellShift;
    innerGlass.rotation.y = glass.rotation.y;
    glassEdge.position.copy(glass.position);
    glassEdge.rotation.y = glass.rotation.y;
    liquid.position.set(liquidShift, 1.255, .018 * progress);
    meniscus.position.set(liquidShift, 1.982, .018 * progress);
    label.position.x = shellShift;
    base.position.x = shellShift;
    neck.position.x = shellShift;

    const plume = openingMotion ? Math.sin(Math.min(1, Math.max(0, progress)) * Math.PI) : 0;
    mistMaterial.opacity = plume * .18;
    mist.scale.setScalar(.84 + progress * .22);
    sprayLight.intensity = plume * .52;

    camera.lookAt(.05 * progress, 1.76 + progress * .18, 0);
    camera.fov = framingFov + progress * 4.2;
    camera.updateProjectionMatrix();
  }

  function draw() {
    const drawStarted = performance.now();
    renderer.info.autoReset = false;
    renderer.info.reset();
    label.visible = false;
    glass.visible = false;
    glassEdge.visible = false;
    innerGlass.visible = false;
    base.visible = false;
    neck.visible = false;
    renderer.setRenderTarget(refractionTarget);
    renderer.render(scene, camera);
    label.visible = true;
    glass.visible = true;
    glassEdge.visible = true;
    innerGlass.visible = true;
    base.visible = true;
    neck.visible = true;
    renderer.setRenderTarget(null);
    renderer.render(scene, camera);
    host.dataset.renderDurationMs = (performance.now() - drawStarted).toFixed(2);
    renderCount += 1;
    host.dataset.renderCount = String(renderCount);
    host.dataset.triangles = String(renderer.info.render.triangles);
    host.dataset.drawCalls = String(renderer.info.render.calls);
    host.dataset.capY = cap.position.y.toFixed(4);
    host.dataset.atomizerY = atomizer.position.y.toFixed(4);
    host.dataset.liquidY = liquid.position.y.toFixed(4);
    host.dataset.glassY = glass.position.y.toFixed(4);
    host.dataset.mistOpacity = mistMaterial.opacity.toFixed(4);
  }

  function tick(time: number) {
    frame = 0;
    host.dataset.framePending = "false";
    if (disposed || !visible || document.hidden) return;
    let needsAnotherFrame = false;
    if (explored !== exploreTarget) {
      const elapsed = options.reducedMotion ? 1 : Math.min(1, (time - transitionStart) / 880);
      const eased = elapsed < .5 ? 4 * elapsed * elapsed * elapsed : 1 - Math.pow(-2 * elapsed + 2, 3) / 2;
      explored = startProgress + (exploreTarget - startProgress) * eased;
      updateParts(explored);
      if (elapsed === 1) explored = exploreTarget;
      else needsAnotherFrame = true;
    }
    if (rotating) {
      rotation.x += (target.x - rotation.x) * .17;
      rotation.y += (target.y - rotation.y) * .17;
      assembly.rotation.x = rotation.x;
      assembly.rotation.y = rotation.y;
      rotating = Math.abs(rotation.x - target.x) + Math.abs(rotation.y - target.y) > .0005;
      needsAnotherFrame = needsAnotherFrame || rotating;
    }
    assembly.rotation.y = rotation.y + explored * .13;
    draw();
    if (needsAnotherFrame) requestDraw();
  }

  function requestDraw() {
    if (disposed || initializing || frame || !visible || document.hidden) return;
    frame = requestAnimationFrame(tick);
    host.dataset.framePending = "true";
  }

  function resize() {
    const width = Math.max(1, host.clientWidth);
    const height = Math.max(1, host.clientHeight);
    renderer.setSize(width, height, false);
    refractionTarget.setSize(Math.round(width * renderer.getPixelRatio()), Math.round(height * renderer.getPixelRatio()));
    camera.aspect = width / height;
    framingFov = window.matchMedia("(max-width: 600px)").matches ? 27 : 30;
    camera.fov = framingFov + explored * 5;
    camera.updateProjectionMatrix();
    requestDraw();
  }
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(host);
  const visibility = () => {
    if (document.hidden && frame) {
      cancelAnimationFrame(frame);
      frame = 0;
      host.dataset.framePending = "false";
    } else requestDraw();
  };
  document.addEventListener("visibilitychange", visibility);
  const contextLost = (event: Event) => {
    event.preventDefault();
    options.onContextLost();
  };
  renderer.domElement.addEventListener("webglcontextlost", contextLost);
  const controller: PerfumeSpatialController = {
    setExplored(value, immediate = false) {
      if (disposed) return;
      startProgress = explored;
      exploreTarget = value ? 1 : 0;
      openingMotion = exploreTarget > startProgress;
      transitionStart = performance.now();
      if (immediate) {
        explored = exploreTarget;
        updateParts(explored);
        assembly.rotation.y = rotation.y + explored * .13;
        if (visible && !document.hidden) draw();
      } else requestDraw();
    },
    setPointer(x, y) {
      if (disposed || options.reducedMotion) return;
      target.x = -.02 + y * .045;
      target.y = -.12 + x * .16;
      rotating = true;
      requestDraw();
    },
    setVisible(value) {
      visible = value;
      if (!value && frame) {
        cancelAnimationFrame(frame);
        frame = 0;
        host.dataset.framePending = "false";
      }
      if (value) requestDraw();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      didDispose = true;
      cancelAnimationFrame(frame);
      host.dataset.framePending = "false";
      resizeObserver.disconnect();
      document.removeEventListener("visibilitychange", visibility);
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      const geometries = new Set<THREE.BufferGeometry>();
      const materials = new Set<THREE.Material>();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          geometries.add(object.geometry);
          (Array.isArray(object.material) ? object.material : [object.material]).forEach((material) => materials.add(material));
        }
      });
      geometries.forEach((geometry) => geometry.dispose());
      materials.forEach((material) => material.dispose());
      labelMap.dispose();
      backdropMap.dispose();
      shadowMap.dispose();
      mistMap.dispose();
      environment.dispose();
      refractionTarget.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    },
  };
  resize();
  try {
    await renderer.compileAsync(scene, camera);
    initializing = false;
    visible = options.isVisible?.() ?? visible;
    if (visible && !document.hidden) draw();
    return controller;
  } catch (error) {
    controller.dispose();
    throw error;
  }
  } catch (error) {
    // Setup can fail before the controller exists (PMREM or framebuffer support).
    // Context loss releases every allocated GPU resource even on that early path.
    if (!didDispose) {
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    }
    throw error;
  }
}
