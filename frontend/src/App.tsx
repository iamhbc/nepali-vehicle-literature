import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Layout, MetaProvider } from "./components/Layout";
import Home from "./pages/Home";

// Route-level code splitting keeps the first load small on slow mobile networks.
const Analyze = lazy(() => import("./pages/Analyze"));
const Scan = lazy(() => import("./pages/Scan"));
const Corpus = lazy(() => import("./pages/Corpus"));
const PhraseDetail = lazy(() => import("./pages/PhraseDetail"));
const Explore = lazy(() => import("./pages/Explore"));
const Method = lazy(() => import("./pages/Method"));
const AdminApp = lazy(() => import("./pages/admin/AdminApp"));

function Loading() {
  return (
    <div className="container page" aria-busy="true">
      <div className="skeleton" style={{ height: 220 }} />
    </div>
  );
}

function NotFound() {
  return (
    <div className="container page">
      <h1 lang="ne">बाटो बिरायो</h1>
      <p>This road doesn't go anywhere. </p>
      <Link to="/">Back to the start</Link>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <MetaProvider>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Home />} />
              <Route path="analyze" element={<Analyze />} />
              <Route path="analysis/:id" element={<Analyze />} />
              <Route path="scan" element={<Scan />} />
              <Route path="corpus" element={<Corpus />} />
              <Route path="corpus/:id" element={<PhraseDetail />} />
              <Route path="explore" element={<Explore />} />
              <Route path="method" element={<Method />} />
              <Route path="admin/*" element={<AdminApp />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </MetaProvider>
    </BrowserRouter>
  );
}
