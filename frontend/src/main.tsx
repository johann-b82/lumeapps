import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import "./i18n";
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
