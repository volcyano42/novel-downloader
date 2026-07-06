import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Reader, ReaderSkeleton } from "./Reader";
import { storageApi, type ChapterBrief } from "@/api/storage";

export default function ReaderPage() {
  const { novelId, chapterId } = useParams<{ novelId: string; chapterId: string }>();
  const navigate = useNavigate();
  const [chapters, setChapters] = useState<ChapterBrief[]>([]);
  const [content, setContent] = useState("");
  const [currentId, setCurrentId] = useState("");
  const [author, setAuthor] = useState("");
  const [loading, setLoading] = useState(true);
  const loadingRef = useRef(false);

  useEffect(() => {
    if (!novelId) return;
    storageApi.listChapters(novelId).then(setChapters).catch(() => {});
    storageApi.getMeta(novelId).then(m => setAuthor(m.author)).catch(() => {});
  }, [novelId]);

  useEffect(() => {
    if (!novelId || !chapterId) return;
    let cancelled = false;
    loadingRef.current = true;
    setLoading(true);
    storageApi.getChapter(novelId, chapterId).then(c => {
      if (cancelled) return;
      setContent(c.content ?? "(空章节)");
      setCurrentId(chapterId);
    }).catch(() => {}).finally(() => {
      if (!cancelled) { setLoading(false); loadingRef.current = false; }
    });
    return () => { cancelled = true; };
  }, [novelId, chapterId]);

  const handleNavigate = useCallback((cid: string) => {
    if (loadingRef.current) return;
    navigate(`/novel/${novelId}/${cid}`, { replace: true });
  }, [novelId, navigate]);

  const currentTitle = chapters.find(ch => ch.id === currentId)?.title ?? "";

  if (loading || !content) return <ReaderSkeleton />;

  return (
    <Reader
      title={currentTitle}
      content={content}
      chapters={chapters.map(ch => ({ id: ch.id, title: ch.title, url: ch.url }))}
      currentChapterId={currentId}
      onNavigate={handleNavigate}
      author={author}
      onBack={() => navigate(`/novel/${novelId}`)}
    />
  );
}
