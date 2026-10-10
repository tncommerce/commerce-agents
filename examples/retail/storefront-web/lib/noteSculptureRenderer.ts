/** Original abstract geometry, not a bottle model or molecular representation.
 * Draws on demand only; no render loop, remote assets, textures or dependencies.
 */
export function createNoteSculptureRenderer(
  canvas: HTMLCanvasElement,
  counts: number[],
  onLost: () => void,
) {
  const gl = canvas.getContext("webgl", {
    alpha: true,
    antialias: false,
    powerPreference: "low-power",
    failIfMajorPerformanceCaveat: true,
  });
  if (!gl) throw new Error("WebGL unavailable");
  const shaders: WebGLShader[] = [];
  let program: WebGLProgram | null = null;
  let buffer: WebGLBuffer | null = null;
  let frame = 0;
  let disposed = false;
  let angle = 0.25;
  let selected = 0;
  function dispose() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(frame);
    observer?.disconnect();
    canvas.removeEventListener("webglcontextlost", lost);
    if (buffer) gl!.deleteBuffer(buffer);
    if (program) gl!.deleteProgram(program);
    shaders.forEach((shader) => gl!.deleteShader(shader));
    gl!.getExtension("WEBGL_lose_context")?.loseContext();
  }
  let observer: ResizeObserver | undefined;
  function lost(event: Event) {
    event.preventDefault();
    dispose();
    onLost();
  }
  try {
    function shader(kind: number, source: string) {
      const value = gl!.createShader(kind);
      if (!value) throw new Error("Shader unavailable");
      shaders.push(value);
      gl!.shaderSource(value, source);
      gl!.compileShader(value);
      if (!gl!.getShaderParameter(value, gl!.COMPILE_STATUS))
        throw new Error("Shader compilation failed");
      return value;
    }
    program = gl.createProgram();
    if (!program) throw new Error("Program unavailable");
    gl.attachShader(
      program,
      shader(
        gl.VERTEX_SHADER,
        `
      attribute vec4 point;
      uniform float angle, focus, aspect, size;
      varying float layer, strength;
      void main() {
        float x = point.x*cos(angle)+point.z*sin(angle);
        float z = -point.x*sin(angle)+point.z*cos(angle);
        float y = point.y*0.92-z*0.22;
        float depth = 3.8-z*0.65;
        gl_Position = vec4(x*2.5/aspect/depth, y*2.5/depth, -z*0.1, 1.0);
        gl_PointSize = size/depth;
        layer = point.w;
        strength = abs(point.w-focus)<0.1 ? 1.0 : 0.38;
      }`,
      ),
    );
    gl.attachShader(
      program,
      shader(
        gl.FRAGMENT_SHADER,
        `
      precision mediump float;
      varying float layer, strength;
      void main() {
        vec2 xy = gl_PointCoord*2.0-1.0;
        float radius = dot(xy,xy);
        if(radius>1.0) discard;
        vec3 normal = vec3(xy.x,-xy.y,sqrt(1.0-radius));
        float light = 0.58+0.42*max(dot(normal,normalize(vec3(-0.6,0.8,1.0))),0.0);
        vec3 color = layer<0.5 ? vec3(0.55,0.70,0.48) : layer<1.5 ? vec3(0.77,0.51,0.47) : vec3(0.64,0.48,0.30);
        color = mix(vec3(0.88,0.89,0.83), color*light, strength);
        gl_FragColor = vec4(color,1.0);
      }`,
      ),
    );
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS))
      throw new Error("Program linking failed");
    const points: number[] = [];
    counts.forEach((count, layer) => {
      const total = Math.min(count, 12);
      for (let i = 0; i < total; i++) {
        const theta = (i / total) * Math.PI * 2 + layer * 0.8;
        points.push(
          Math.cos(theta) * 0.95,
          (1 - layer) * 0.7,
          Math.sin(theta) * 0.72,
          layer,
        );
      }
    });
    buffer = gl.createBuffer();
    if (!buffer) throw new Error("Buffer unavailable");
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(points), gl.STATIC_DRAW);
    gl.useProgram(program);
    const location = gl.getAttribLocation(program, "point");
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location, 4, gl.FLOAT, false, 0, 0);
    gl.enable(gl.DEPTH_TEST);
    const uniforms = Object.fromEntries(
      ["angle", "focus", "aspect", "size"].map((name) => [
        name,
        gl.getUniformLocation(program!, name),
      ]),
    );
    function draw() {
      frame = 0;
      if (disposed || !program) return;
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      gl!.viewport(0, 0, canvas.width, canvas.height);
      gl!.clearColor(0, 0, 0, 0);
      gl!.clear(gl!.COLOR_BUFFER_BIT | gl!.DEPTH_BUFFER_BIT);
      gl!.uniform1f(uniforms.angle, angle);
      gl!.uniform1f(uniforms.focus, selected);
      gl!.uniform1f(uniforms.aspect, canvas.width / canvas.height);
      const maxPoint = gl!.getParameter(
        gl!.ALIASED_POINT_SIZE_RANGE,
      )[1] as number;
      gl!.uniform1f(
        uniforms.size,
        Math.min(canvas.height * 0.43, maxPoint * 3),
      );
      gl!.drawArrays(gl!.POINTS, 0, points.length / 4);
    }
    function schedule() {
      if (!disposed && !frame) frame = requestAnimationFrame(draw);
    }
    observer = new ResizeObserver(schedule);
    observer.observe(canvas);
    canvas.addEventListener("webglcontextlost", lost);
    schedule();
    return {
      update(nextAngle: number, nextSelected: number) {
        angle = nextAngle;
        selected = nextSelected;
        schedule();
      },
      dispose,
    };
  } catch (error) {
    dispose();
    throw error;
  }
}
