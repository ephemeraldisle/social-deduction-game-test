import {loadPyodide} from "./runtime/314.0.7/pyodide.mjs";

let runtime, app, initialization, storageFailure;
let queue = Promise.resolve();
function sync(populate) {
  return new Promise((resolve, reject) => runtime.FS.syncfs(populate, error => error ? reject(error) : resolve()));
}
async function initialize(scope) {
  self.postMessage({progress: "Loading the game…"});
  runtime = await loadPyodide({indexURL: new URL("./runtime/314.0.7/", import.meta.url).href});
  const response = await fetch(new URL("./game.zip", import.meta.url), {cache: "no-cache"});
  if (!response.ok) throw new Error("The game files could not be downloaded. Check your connection and reload.");
  runtime.unpackArchive(await response.arrayBuffer(), "zip", {extractDir: "/app"});
  runtime.FS.chdir("/app");
  runtime.runPython("import sys; sys.path.insert(0, '/app')");
  const root = "/saved-games-" + encodeURIComponent(scope);
  runtime.FS.mkdirTree(root);
  runtime.FS.mount(runtime.FS.filesystems.IDBFS, {}, root);
  self.postMessage({progress: "Opening your saved tables…"});
  await sync(true);
  // Fail visibly if browser storage is blocked or full, before offering play.
  runtime.FS.writeFile(root + "/.storage-check", "ready");
  await sync(false);
  runtime.globals.set("save_root", root);
  app = runtime.runPython("from mission_game.browser import BrowserApp\nBrowserApp(save_root, '/app/examples')");
}
self.onmessage = ({data}) => {
  queue = queue.then(async () => {
    try {
      if (storageFailure) throw new Error(storageFailure);
      initialization ||= initialize(data.scope);
      await initialization;
      await sync(true);
      const result = JSON.parse(app.request_json(data.path, data.payload ?? ""));
      if (data.payload !== null) {
        try { await sync(false); }
        catch (_) {
          storageFailure = "Your last change could not be saved. Free browser storage and reload before continuing.";
          throw new Error(storageFailure);
        }
      }
      self.postMessage({id: data.id, ...result});
    } catch (error) {
      self.postMessage({id: data.id, error: error.message || "Local storage is unavailable. Enable browser storage and reload."});
    }
  });
};
