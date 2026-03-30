import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { MemeUiProvider } from "./context/MemeUiContext";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <MemeUiProvider>
        <App />
      </MemeUiProvider>
    </BrowserRouter>
  </StrictMode>
);
