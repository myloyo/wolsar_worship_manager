import ReactDOM from "react-dom/client";
import App from "./App";
import ThemeProvider from "./ThemeProvider";
import "./styles.scss";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <ThemeProvider>
    <App />
  </ThemeProvider>,
);
