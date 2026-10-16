import * as THREE from "three";

/** Entire scene is original procedural geometry. No models, HDRIs or remote textures. */
export type PerfumeSpatialController = {
  setExplored(value: boolean, immediate?: boolean): void;
  setPointer(x: number, y: number): void;
  setVisible(value: boolean): void;
  dispose(): void;
};

type Options = { reducedMotion: boolean; isVisible?(): boolean; onContextLost(): void };

function bevelledBody(width: number, height: number, depth: number, bevel: number, surface: "rounded" | "flat-fill" = "rounded") {
  const segments = 96;
  const positions: number[] = [];
  const indices: number[] = [];
  const half = height / 2;
  // The perfume vessel is a rounded solid. Actual liquid must NOT repeat its
  // rounded top: a horizontal free surface is the strongest visual cue that the
  // amber volume is a liquid fill, not a smaller opaque bottle inside the glass.
  const profiles = surface === "flat-fill" ? [
    [-half, .90], [-half + bevel * .35, .96], [-half + bevel, .995],
    [-half + bevel * 1.5, 1], [half - .09, 1],
    [half - .02, .997], [half, .987],
  ] : [
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

function liquidRim(width: number, depth: number) {
  const vertices: THREE.Vector3[] = [];
  // The line follows the same square-shouldered superellipse as the liquid.
  // Its narrow, continuous specular edge communicates a real fill level.
  for (let i = 0; i < 96; i++) {
    const angle = i / 96 * Math.PI * 2;
    const x = Math.cos(angle), z = Math.sin(angle);
    vertices.push(new THREE.Vector3(
      Math.sign(x) * Math.pow(Math.abs(x), .48) * width / 2,
      0,
      Math.sign(z) * Math.pow(Math.abs(z), .48) * depth / 2,
    ));
  }
  return new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(vertices),
    new THREE.LineBasicMaterial({ color: 0xf7d5a7, transparent: true, opacity: .32, depthWrite: false }),
  );
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
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, premultipliedAlpha: false, powerPreference: "high-performance" });
  let didDispose = false;
  try {
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, window.innerWidth < 768 ? 1.35 : 1.65));
  renderer.setClearColor(0xeee8de, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .88;
  renderer.domElement.setAttribute("aria-hidden", "true");
  renderer.domElement.setAttribute("data-spatial-webgl", "true");
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = null;
  const camera = new THREE.PerspectiveCamera(28, 1, .1, 60);
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
  panel(1.15, 9.5, [-4.4, 2.3, 6.8], 0xfff8e8, 5.1);
  panel(.36, 8.5, [4.25, 2.25, 5.7], 0xf8fbff, 4.1);
  panel(5.5, 3.4, [-.3, 8.2, .2], 0xfff3dd, 1.9);
  panel(2.2, 7.5, [1.1, 2.6, -6], 0xffc66f, 1.55);
  panel(1.0, 8.5, [2.8, 2.0, 6.5], 0x25231f, 1.1);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const environment = pmrem.fromScene(studio, .035, .1, 30);
  scene.environment = environment.texture;
  scene.environmentIntensity = .86;
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
  studioGlow.addColorStop(0, "rgba(244,232,212,.55)");
  studioGlow.addColorStop(.42, "rgba(225,211,192,.30)");
  studioGlow.addColorStop(.72, "rgba(193,167,137,.09)");
  studioGlow.addColorStop(1, "rgba(231,218,199,0)");
  backdropContext.fillStyle = studioGlow;
  backdropContext.fillRect(0, 0, 1024, 1024);
  const studioShade = backdropContext.createLinearGradient(360, 170, 920, 700);
  studioShade.addColorStop(0, "rgba(74,55,36,0)");
  studioShade.addColorStop(.28, "rgba(74,55,36,0)");
  studioShade.addColorStop(.48, "rgba(74,55,36,.19)");
  studioShade.addColorStop(.61, "rgba(58,42,27,.16)");
  studioShade.addColorStop(.78, "rgba(58,42,27,.035)");
  studioShade.addColorStop(1, "rgba(58,42,27,0)");
  backdropContext.fillStyle = studioShade;
  backdropContext.fillRect(0, 0, 1024, 1024);
  const backdropMap = new THREE.CanvasTexture(backdropCanvas);
  backdropMap.colorSpace = THREE.SRGBColorSpace;
  const backdrop = new THREE.Mesh(new THREE.PlaneGeometry(10.2, 10.2), new THREE.MeshBasicMaterial({
    map: backdropMap, transparent: true, opacity: .86, depthWrite: false, toneMapped: false,
  }));
  backdrop.position.set(-1.4, 1.7, -3.6);
  backdrop.quaternion.copy(camera.quaternion);
  scene.add(backdrop);

  // A photographed perfume needs a *rear* studio reflector to show light
  // travelling through its coloured volume. This is a real plane in the
  // refraction scene, NOT a 2D tint painted over the bottle on the page.
  // A softly bounded card keeps the center transmissive and creates useful
  // optical variation without a rectangular background panel in the hero.
  const rearCardCanvas = document.createElement("canvas");
  rearCardCanvas.width = 128;
  rearCardCanvas.height = 256;
  const rearCardContext = rearCardCanvas.getContext("2d")!;
  const rearCardGradient = rearCardContext.createLinearGradient(0, 0, 128, 0);
  rearCardGradient.addColorStop(0, "rgba(255,247,227,0)");
  rearCardGradient.addColorStop(.16, "rgba(255,247,227,.02)");
  rearCardGradient.addColorStop(.40, "rgba(255,247,227,.48)");
  rearCardGradient.addColorStop(.57, "rgba(255,252,242,.76)");
  rearCardGradient.addColorStop(.76, "rgba(255,247,227,.25)");
  rearCardGradient.addColorStop(1, "rgba(255,247,227,0)");
  rearCardContext.fillStyle = rearCardGradient;
  rearCardContext.fillRect(0, 0, 128, 256);
  const rearCardMap = new THREE.CanvasTexture(rearCardCanvas);
  rearCardMap.colorSpace = THREE.SRGBColorSpace;
  const rearCard = new THREE.Mesh(new THREE.PlaneGeometry(1.28, 4.1), new THREE.MeshBasicMaterial({
    map: rearCardMap, transparent: true, opacity: .68, depthWrite: false, toneMapped: false,
  }));
  rearCard.position.set(-.47, 1.66, -2.35);
  rearCard.quaternion.copy(camera.quaternion);
  rearCard.renderOrder = 0;
  scene.add(rearCard);

  const hemisphere = new THREE.HemisphereLight(0xfffcf3, 0x71604b, .48);
  scene.add(hemisphere);
  const key = new THREE.DirectionalLight(0xfff9eb, 1.25);
  key.position.set(-5, 6, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xffffff, .9);
  rim.position.set(3, 4, -4);
  scene.add(rim);

  const assembly = new THREE.Group();
  assembly.rotation.set(-.02, -.12, -.035);
  assembly.position.y = -.11;
  scene.add(assembly);

  const glassMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, roughness: .003, metalness: 0, transmission: 1,
    // Keep this in the opaque renderer queue so the physically transmitted
    // light samples the valid studio capture, not the transparent queue's
    // uninitialized transmission target. The fragment shader writes an
    // authored alpha straight into the alpha canvas (no GL blending needed).
    // premultipliedAlpha:false lets CSS supply the genuine page background.
    thickness: .095, ior: 1.50, envMapIntensity: 1.22, dispersion: .006,
    attenuationColor: new THREE.Color(0xffffff), attenuationDistance: 140,
    clearcoat: .18, clearcoatRoughness: .006,
  });
  const refractionType = renderer.extensions.has("EXT_color_buffer_half_float") || renderer.extensions.has("EXT_color_buffer_float")
    ? THREE.HalfFloatType : THREE.UnsignedByteType;
  // Physical transmission uses bicubic mip sampling: the target must supply all LODs.
  const refractionTarget = new THREE.WebGLRenderTarget(1, 1, {
    type: refractionType, samples: 2, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter,
  });
  const studyEyeLocal = new THREE.Vector3();
  const studyVolumeShader = "\n#ifdef USE_TRANSMISSION\nuniform vec3 studyEyeInBottle;\nvarying vec3 vStudyBottlePoint;\nvarying vec3 vStudyBottleNormal;\n\n// Air -> silica glass -> hollow interior, approximated by a bounded refracted\n// ray inside the actual superellipse cavity. The perfume's free surface is\n// horizontal. Glass reflection stays in the stock MeshPhysical BRDF; only the\n// TRANSMITTED light receives perfume's Beer-Lambert absorption.\nfloat studyLiquidPath(vec3 entry, vec3 exteriorNormal) {\n  vec3 fromEye = normalize(entry - studyEyeInBottle);\n  vec3 insideRay = refract(fromEye, normalize(exteriorNormal), 1.0 / 1.50);\n  if (dot(insideRay, insideRay) < 0.01) insideRay = fromEye;\n\n  // Local dimensions: inner glass 2.055 x 1.005, liquid inset at walls,\n  // flat top at world y=1.985, base y=.345; bottle origin world y=1.42.\n  vec3 innerStart = entry + insideRay * 0.077;\n  vec3 boundsMin = vec3(-1.023, -1.075, -0.495);\n  vec3 boundsMax = vec3( 1.023,  0.565,  0.495);\n  vec3 safeRay = sign(insideRay) * max(abs(insideRay), vec3(0.0001));\n  vec3 t0 = (boundsMin - innerStart) / safeRay;\n  vec3 t1 = (boundsMax - innerStart) / safeRay;\n  vec3 earliest = min(t0, t1);\n  vec3 latest = max(t0, t1);\n  float nearDistance = max(0.0, max(earliest.x, max(earliest.y, earliest.z)));\n  float farDistance = min(latest.x, min(latest.y, latest.z));\n  if (farDistance <= nearDistance) return 0.0;\n  float raySpan = min(farDistance - nearDistance, 2.55);\n  float submerged = 0.0;\n  for (int sampleIndex = 0; sampleIndex < 8; sampleIndex++) {\n    float t = nearDistance + raySpan * (float(sampleIndex) + 0.5) / 8.0;\n    vec3 q = innerStart + insideRay * t;\n    float section = pow(abs(q.x / 1.023), 4.1666667)\n      + pow(abs(q.z / .495), 4.1666667);\n    float wall = 1.0 - smoothstep(.94, 1.025, section);\n    float floorProfile = smoothstep(-1.08, -.96, q.y);\n    submerged += wall * floorProfile;\n  }\n  return raySpan * submerged / 8.0;\n}\n#endif\n";
  glassMaterial.onBeforeCompile = (shader) => {
    shader.uniforms.studioRefractionMap = { value: refractionTarget.texture };
    shader.uniforms.studyEyeInBottle = { value: studyEyeLocal };
    shader.vertexShader = shader.vertexShader.replace("#include <common>",
      "#include <common>\nvarying vec3 vStudyBottlePoint;\nvarying vec3 vStudyBottleNormal;");
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>",
      "#include <begin_vertex>\nvStudyBottlePoint = position;\nvStudyBottleNormal = normal;");
    shader.fragmentShader = shader.fragmentShader.replace("#include <common>",
      "#include <common>\n" + studyVolumeShader);
    shader.fragmentShader = shader.fragmentShader.replace("#include <transmission_pars_fragment>",
      THREE.ShaderChunk.transmission_pars_fragment.replaceAll("transmissionSamplerMap", "studioRefractionMap"));
    const physicalTransmission = THREE.ShaderChunk.transmission_fragment;
    const transmissionMix = "totalDiffuse = mix( totalDiffuse, transmitted.rgb, material.transmission );";
    if (!physicalTransmission.includes(transmissionMix)) {
      throw new Error("Three.js transmission contract changed; do not silently omit glass/liquid coupling");
    }
    shader.fragmentShader = shader.fragmentShader.replace("#include <transmission_fragment>",
      physicalTransmission.replace(transmissionMix, "float studyPathLength = studyLiquidPath(vStudyBottlePoint, vStudyBottleNormal);\n    vec3 studyAbsorption = exp(-vec3(0.14, 0.56, 1.30) * studyPathLength);\n    totalDiffuse = mix(totalDiffuse, transmitted.rgb * studyAbsorption, material.transmission);"));
    // The framebuffer transmits the real editorial background through air,
    // while progressively retaining the amber contribution for longer liquid
    // paths. The original specular Fresnel stays on the MeshPhysical material.
    shader.fragmentShader = shader.fragmentShader.replace("#include <opaque_fragment>",
      `#include <opaque_fragment>
      #ifdef USE_TRANSMISSION
        float studyFacing = clamp(abs(dot(normalize(vStudyBottleNormal),
          normalize(studyEyeInBottle - vStudyBottlePoint))), 0.0, 1.0);
        float studyFresnel = pow(1.0 - studyFacing, 3.0);
        float studyVisibleAbsorption = 1.0 - exp(-0.68 * studyPathLength);
        gl_FragColor.a = clamp(.075 + .89 * studyVisibleAbsorption +
          .30 * studyFresnel, .075, .93);
      #endif`);
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
        float alpha = rim * 0.095;
        gl_FragColor = vec4(vec3(1.0, 0.985, 0.95) * (0.72 + rim * 0.55), alpha);
      }
    `,
  });
  const glassEdge = new THREE.Mesh(glass.geometry, glassEdgeMaterial);
  glassEdge.position.copy(glass.position);
  glassEdge.scale.set(1.003, 1.002, 1.008);
  glassEdge.renderOrder = 7;
  assembly.add(glassEdge);

  // Actual inset cavity wall: the outer glass radius is 1.10 x .57,
  // the cavity radius is 1.0275 x .5025. The lower inset yields a
  // structurally thicker transparent base than the side walls.
  // Back-facing specular highlights reveal that empty cavity without
  // painting a diffuse white lining (which previously made it milky).
  const innerGlassMaterial = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, depthTest: true,
    side: THREE.BackSide, blending: THREE.AdditiveBlending,
    vertexShader: `
      varying vec3 vInsideNormal;
      varying vec3 vInsideView;
      void main() {
        vec4 eye = modelViewMatrix * vec4(position, 1.0);
        vInsideNormal = normalize(normalMatrix * normal);
        vInsideView = normalize(-eye.xyz);
        gl_Position = projectionMatrix * eye;
      }
    `,
    fragmentShader: `
      varying vec3 vInsideNormal;
      varying vec3 vInsideView;
      void main() {
        vec3 N = normalize(vInsideNormal);
        vec3 V = normalize(vInsideView);
        float f = pow(1.0 - abs(dot(N, V)), 4.0);
        float key = pow(max(dot(reflect(-normalize(vec3(-0.6,0.3,0.75)), N), V), 0.0), 70.0);
        float intensity = f * .075 + key * .035;
        gl_FragColor = vec4(vec3(1.0, .97, .92) * intensity, 1.0);
      }
    `,
  });
  const innerGlass = new THREE.Mesh(bevelledBody(2.055, 2.26, 1.005, .08), innerGlassMaterial);
  innerGlass.position.set(0, 1.43, 0);
  innerGlass.renderOrder = 3;
  assembly.add(innerGlass);

  // No second coloured liquid mesh: transmission/absorption is coupled in
  // glassMaterial itself. Keep a non-rendering fill transform for interaction
  // contracts and level instrumentation.
  const liquid = new THREE.Group();
  liquid.position.set(0, 1.165, 0);
  assembly.add(liquid);
  // A flat optical surface and its fine bright boundary remain visibly
  // separate from the vertical body. Do not imply motion/sloshing at rest.
  const meniscusMaterial = new THREE.MeshPhysicalMaterial({
    // An interface is nearly clear: the amber belongs to the volume below,
    // not to an opaque golden lid resting on top of the liquid.
    color: 0xfff4de, roughness: .045, metalness: 0, transmission: .94,
    thickness: .012, ior: 1.335, envMapIntensity: 1.0,
    transparent: true, opacity: .15, depthWrite: false, side: THREE.DoubleSide,
    clearcoat: .28, clearcoatRoughness: .025,
  });
  const meniscus = new THREE.Mesh(superellipsePlate(1.96, .89), meniscusMaterial);
  meniscus.position.set(0, 1.987, 0);
  meniscus.renderOrder = 5;
  assembly.add(meniscus);
  const surfaceRim = liquidRim(1.985, .925);
  surfaceRim.position.set(0, 1.991, 0);
  surfaceRim.renderOrder = 6;
  assembly.add(surfaceRim);

  const baseMaterial = new THREE.MeshStandardMaterial({
    color: 0xffffff, roughness: .08, metalness: 0, envMapIntensity: 1.6,
    transparent: true, opacity: .035, depthWrite: false, side: THREE.DoubleSide,
  });
  const base = new THREE.Mesh(bevelledBody(2.03, .13, 1.0, .035), baseMaterial);
  base.position.set(0, .245, 0);
  base.renderOrder = 3;
  assembly.add(base);

  // The metal-neck glass is outside the main bottle/cavity coordinate frame;
  // keep it transmissive but exclude the perfume-volume ray integration.
  const neckGlassMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, roughness: .01, metalness: 0, transmission: 1,
    thickness: .08, ior: 1.50, envMapIntensity: 1.15,
  });
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(.31, .4, .38, 48), neckGlassMaterial);
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
  let framingFov = 28;
  let openingFocusLift = .18;
  let explored = 0;
  let exploreTarget = 0;
  let startProgress = 0;
  let transitionStart = 0;
  let rotating = false;
  let openingMotion = false;
  const rotation = { x: -.02, y: -.12 };
  const target = { ...rotation };

  function updateParts(progress: number) {
    const mobileWidth = host.clientWidth;
    const capRise = mobileWidth < 360 ? .80 : mobileWidth < 601 ? .92 : 1.04;
    const atomizerRise = mobileWidth < 360 ? .24 : mobileWidth < 601 ? .33 : .46;
    cap.position.set(.34 * progress, 3.13 + progress * capRise, .10 * progress);
    cap.rotation.z = progress * -.115;
    cap.rotation.y = progress * .10;
    atomizer.position.set(-.10 * progress, 2.77 + progress * atomizerRise, .07 * progress);
    atomizer.rotation.z = progress * .045;
    const shellShift = -.095 * progress;
    const liquidShift = .085 * progress;
    glass.position.x = shellShift;
    glass.rotation.y = progress * -.025;
    innerGlass.position.x = shellShift;
    innerGlass.rotation.y = glass.rotation.y;
    glassEdge.position.copy(glass.position);
    glassEdge.rotation.y = glass.rotation.y;
    liquid.position.set(liquidShift, 1.165, .018 * progress);
    meniscus.position.set(liquidShift, 1.987, .018 * progress);
    surfaceRim.position.set(liquidShift, 1.991, .018 * progress);
    label.position.x = shellShift;
    base.position.x = shellShift;
    neck.position.x = shellShift;

    const plume = openingMotion ? Math.sin(Math.min(1, Math.max(0, progress)) * Math.PI) : 0;
    mistMaterial.opacity = plume * .18;
    mist.scale.setScalar(.84 + progress * .22);
    sprayLight.intensity = plume * .52;

    // A taller object separation must not clip the cap against the headline
    // in the 320/390px stacked mobile composition.
    camera.lookAt(.05 * progress, 1.76 + progress * openingFocusLift, 0);
    camera.fov = framingFov + progress * 6.2;
    camera.updateProjectionMatrix();
  }

  // The transmissive pass sees an opaque, neutral studio backing even though
  // the public canvas itself must remain transparent in the editorial hero.
  // This prevents undefined clear-alpha pixels from bleaching the glass.
  // The studio target remains opaque while the public editorial canvas is
  // transparent. Its warm mid-tone gives amber transmitted light room to vary.
  const refractionBacking = new THREE.Color("#d9cabb");

  function draw() {
    // Coupled glass/liquid shader receives the eye in the outer vessel frame.
    // The same shader accounts for both opening rotation and camera reframing.
    studyEyeLocal.copy(camera.position);
    glass.worldToLocal(studyEyeLocal);
    const drawStarted = performance.now();
    renderer.info.autoReset = false;
    renderer.info.reset();
    label.visible = false;
    glass.visible = false;
    glassEdge.visible = false;
    innerGlass.visible = false;
    base.visible = false;
    neck.visible = false;
    meniscus.visible = false;
    surfaceRim.visible = false;
    // Opaque only in the texture the glass samples. Restore the transparent
    // display background and default framebuffer before the public frame.
    const priorBackground = scene.background;
    try {
      scene.background = refractionBacking;
      backdrop.visible = true;
      renderer.setRenderTarget(refractionTarget);
      renderer.render(scene, camera);
    } finally {
      scene.background = priorBackground;
      renderer.setRenderTarget(null);
    }
    // The gradient stage is valuable INSIDE the glass refraction capture,
    // but must not show as a rectangular plane behind the bottle on screen.
    backdrop.visible = false;
    rearCard.visible = false;
    label.visible = true;
    meniscus.visible = true;
    surfaceRim.visible = true;
    glass.visible = true;
    glassEdge.visible = true;
    innerGlass.visible = true;
    base.visible = true;
    neck.visible = true;
    try {
      renderer.render(scene, camera);
    } finally {
      backdrop.visible = true;
      rearCard.visible = true;
    }
    host.dataset.renderDurationMs = (performance.now() - drawStarted).toFixed(2);
    renderCount += 1;
    host.dataset.renderCount = String(renderCount);
    host.dataset.triangles = String(renderer.info.render.triangles);
    host.dataset.drawCalls = String(renderer.info.render.calls);
    host.dataset.capY = cap.position.y.toFixed(4);
    const capCrest = cap.localToWorld(new THREE.Vector3(0, .372, 0)).project(camera);
    host.dataset.capTopViewportY = (host.getBoundingClientRect().top +
      (1 - capCrest.y) * host.clientHeight / 2).toFixed(2);
    host.dataset.atomizerY = atomizer.position.y.toFixed(4);
    host.dataset.liquidY = liquid.position.y.toFixed(4);
    host.dataset.liquidOptics = "translucent-volume";
    host.dataset.liquidAbsorption = "glass-coupled-ray-volume";
    host.dataset.liquidSurfaceY = meniscus.position.y.toFixed(4);
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
    framingFov = window.matchMedia("(max-width: 600px)").matches ? 25 : 28;
    openingFocusLift = width < 360 ? .44 : width < 601 ? .31 : .18;
    camera.lookAt(.05 * explored, 1.76 + explored * openingFocusLift, 0);
    camera.fov = framingFov + explored * 6.2;
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
      surfaceRim.geometry.dispose();
      surfaceRim.material.dispose();
      labelMap.dispose();
      backdropMap.dispose();
      rearCardMap.dispose();
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
