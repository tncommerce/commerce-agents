import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";

function option(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1]
    ? process.argv[index + 1]
    : fallback;
}

const root = path.resolve(option("--root", "out"));
const port = Number(option("--port", "3000"));

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function safeRelativePath(requestUrl) {
  const pathname = decodeURIComponent(
    new URL(requestUrl || "/", "http://127.0.0.1").pathname,
  );
  return path.posix.normalize(pathname).replace(/^\/+/, "");
}

async function resolveFile(relativePath) {
  const candidates = relativePath
    ? [
        relativePath,
        `${relativePath}.html`,
        path.join(relativePath, "index.html"),
      ]
    : ["index.html"];

  for (const candidate of candidates) {
    const fullPath = path.resolve(root, candidate);
    if (fullPath !== root && !fullPath.startsWith(`${root}${path.sep}`)) {
      continue;
    }

    try {
      const info = await stat(fullPath);
      if (info.isFile()) return { fullPath, info };
    } catch {
      // Try the next clean-URL candidate.
    }
  }

  return null;
}

const server = createServer(async (request, response) => {
  if (!["GET", "HEAD"].includes(request.method || "GET")) {
    response.writeHead(405, { Allow: "GET, HEAD" });
    response.end();
    return;
  }

  try {
    const relativePath = safeRelativePath(request.url);
    const resolved = await resolveFile(relativePath);

    if (!resolved) {
      const fallback = await resolveFile("404");
      if (!fallback) {
        response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        response.end("Not found");
        return;
      }

      response.writeHead(404, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Length": fallback.info.size,
      });
      if (request.method === "HEAD") {
        response.end();
      } else {
        createReadStream(fallback.fullPath).pipe(response);
      }
      return;
    }

    const extension = path.extname(resolved.fullPath).toLowerCase();
    response.writeHead(200, {
      "Content-Type": contentTypes[extension] || "application/octet-stream",
      "Content-Length": resolved.info.size,
      "Cache-Control": "no-store",
    });

    if (request.method === "HEAD") {
      response.end();
    } else {
      createReadStream(resolved.fullPath).pipe(response);
    }
  } catch (error) {
    response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    response.end(error instanceof Error ? error.message : "Server error");
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`DUFYND static export served from ${root} on http://127.0.0.1:${port}`);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
