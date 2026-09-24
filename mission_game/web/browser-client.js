/* Loaded only by the static build. All game commands stay on this device. */
"use strict";
(() => {
  const source = new URL(document.currentScript.src);
  const workerURL = new URL("browser-worker.js", source);
  workerURL.search = source.search;
  const scope = new URL(".", source).pathname;
  let worker, failure, nextID = 0;
  const pending = new Map();
  function fail(message) {
    failure = new Error(message);
    for (const {reject} of pending.values()) reject(failure);
    pending.clear();
    worker?.terminate();
  }
  function send(path, payload) {
    if (failure) return Promise.reject(failure);
    if (!worker) {
      worker = new Worker(workerURL, {type: "module"});
      worker.onmessage = ({data}) => {
        if (data.progress) {
          const heading = document.querySelector("#app .loading h1");
          if (heading) heading.textContent = data.progress;
          return;
        }
        const request = pending.get(data.id);
        if (!request) return;
        pending.delete(data.id);
        if (data.error) request.reject(new Error(data.error));
        else if (data.status >= 400) {
          const error = new Error(data.data.error.message);
          error.status = data.status;
          request.reject(error);
        } else request.resolve(data.data);
      };
      worker.onerror = () => fail("The game could not load. Check your connection, then reload this page.");
      worker.onmessageerror = () => fail("The game worker stopped responding. Reload to resume your saved table.");
    }
    return new Promise((resolve, reject) => {
      const id = ++nextID;
      pending.set(id, {resolve, reject});
      worker.postMessage({id, path, scope, payload: payload === undefined ? null : JSON.stringify(payload)});
    });
  }
  window.MissionBrowser = {
    request(path, payload) {
      if (!window.Worker || !window.indexedDB || !navigator.locks) {
        return Promise.reject(new Error("This game needs a current browser with local storage enabled. Try Chrome, Firefox, Safari, or Edge."));
      }
      // Each tab reloads saved files under the same lock before acting, so a
      // stale tab receives the engine's revision conflict instead of overwriting.
      return navigator.locks.request(`hidden-rules:${scope}`, () => send(path, payload));
    }
  };
})();
