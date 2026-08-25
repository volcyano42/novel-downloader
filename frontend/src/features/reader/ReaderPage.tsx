import {useCallback, useEffect, useRef, useState} from "react";
import {useNavigate, useParams} from "react-router-dom";
import {Reader, ReaderSkeleton} from "./Reader";
import {useChapter, useChapters, useNovelMeta} from "@/hooks/index";

export default function ReaderPage() {
  const { novelId, chapterId } = useParams<{ novelId: string; chapterId: string }>();
  const navigate = useNavigate();
  const [currentId, setCurrentId] = useState("");
  const loadingRef = useRef(false);

  const { data: chapters = [] } = useChapters(novelId);
  const { data: chapter, isLoading: loading } = useChapter(novelId, chapterId);
  const { data: meta } = useNovelMeta(novelId);
  const content = chapter?.content ?? "";

  // 进入/换章时置顶（依赖 content：内容加载完成后再次回顶，避免滚动位置被新内容撑开）
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [chapterId, content]);

  useEffect(() => {
    if (chapter) {
      setCurrentId(chapter.id);
      loadingRef.current = false;
    }
  }, [chapter]);

  const handleNavigate = useCallback((cid: string) => {
    if (loadingRef.current) return;
    navigate(`/novel/${novelId}/${cid}`);
  }, [novelId, navigate]);

  const currentTitle = chapters.find(ch => ch.id === currentId)?.title ?? "";

  if (loading || !content) return <ReaderSkeleton />;

  return (
    <Reader
      title={currentTitle}
      content={content}
      images={chapter?.images ?? []}
      chapters={chapters.map(ch => ({ id: ch.id, title: ch.title, url: ch.url }))}
      currentChapterId={currentId}
      onNavigate={handleNavigate}
      author={meta?.author ?? ""}
      onBack={() => { if (window.history.length > 1) navigate(-1); else navigate(`/novel/${novelId}`); }}
    />
  );
}
