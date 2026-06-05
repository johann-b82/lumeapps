import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import "./i18n";
// PdfPlayer renders in the playlist-editor preview (PlaylistEditorPage). pdf.js
// won't decode without a worker, and the worker is configured globally on this
// import (sets GlobalWorkerOptions.workerSrc). Without this the preview shows
// "Failed to load PDF file" even though the asset request itself succeeds.
import "./player/lib/pdfWorker";
import { bootstrap } from "./bootstrap";

// Block first paint on bootstrap (D-01). Vite 8 transpiles top-level await
// for modern browsers. The splash inside #root in index.html is atomically
// replaced by React's first commit.
await bootstrap();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
