import { useEffect } from "react";
import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import BookshelfPage from "@/features/bookshelf/BookshelfPage";
import DetailPage from "@/features/detail/DetailPage";
import ReaderPage from "@/features/reader/ReaderPage";

export default function App() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/bookshelf" replace />} />
      <Route path="/bookshelf" element={<BookshelfPage />} />
      <Route path="/downloads" element={<BookshelfPage />} />
      <Route path="/settings" element={<BookshelfPage />} />
      <Route path="/search-tab" element={<BookshelfPage />} />
      <Route path="/novel/:novelId" element={<DetailPage />} />
      <Route path="/novel/:novelId/:chapterId" element={<ReaderPage />} />
      <Route path="/search/:novelId" element={<DetailPage />} />
    </Routes>
  );
}
