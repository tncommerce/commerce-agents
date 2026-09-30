const MODEL_VIEWER_SRC =
  "https://unpkg.com/@google/model-viewer@4.3.1/dist/model-viewer.min.js";

let pendingLoad: Promise<void> | null = null;

/** Share one download, but allow a later mount to retry a failed download. */
export function ensureModelViewer(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (customElements.get("model-viewer")) return Promise.resolve();
  if (pendingLoad) return pendingLoad;

  const job = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      'script[data-dufynd-model-viewer="true"]',
    );
    const script = existing || document.createElement("script");
    const cleanup = () => {
      clearTimeout(timer);
      script.removeEventListener("load", onLoad);
      script.removeEventListener("error", onError);
    };
    const fail = () => {
      cleanup();
      script.remove();
      reject(new Error("3D viewer failed to load"));
    };
    const onLoad = () => {
      if (!customElements.get("model-viewer")) {
        fail();
        return;
      }
      cleanup();
      resolve();
    };
    const onError = () => fail();
    const timer = setTimeout(fail, 15_000);
    script.addEventListener("load", onLoad, { once: true });
    script.addEventListener("error", onError, { once: true });
    if (!existing) {
      script.type = "module";
      script.src = MODEL_VIEWER_SRC;
      script.dataset.dufyndModelViewer = "true";
      document.head.appendChild(script);
    }
  });
  pendingLoad = job.catch((error) => {
    pendingLoad = null;
    throw error;
  });
  return pendingLoad;
}
