import {StrictMode} from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter} from "react-router-dom";
import {MutationCache, QueryCache, QueryClient, QueryClientProvider} from "@tanstack/react-query";
import "./index.css";
import App from "./App";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
  queryCache: new QueryCache({
    onError: (error) => console.error("[query]", (error as Error).message),
  }),
  mutationCache: new MutationCache({
    onError: (error) => console.error("[mutation]", (error as Error).message),
  }),
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
