
"use client";
import VideoHistory from "./VideoHistory";
import { useEffect, useState } from "react";

type Video = {
  id: number;
  tiktok_video_id: string;
  url: string;
  description: string | null;
  published_at: string | null;
  views_count: number | null;
  likes_count: number | null;
  comments_count: number | null;
  shares_count: number | null;
  collected_at: string | null;
};

type Summary = {
  videos: number;
  videos_with_views: number;
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  average_views: number | null;
};

type VideosResponse = {
  club_id: number;
  club_name: string;
  total: number;
  page: number;
  page_size: number;
  summary: Summary;
  items: Video[];
};

const formatNumber = (value: number | null) =>
  value === null
    ? "—"
    : new Intl.NumberFormat("pl-PL").format(value);

function Metric({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-white">
        {formatNumber(value)}
      </p>
    </div>
  );
}

export default function VideoAnalytics({
  clubId,
}: {
  clubId: number;
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const [filters, setFilters] = useState({
    start: "",
    end: "",
  });
  const [selectedVideoId, setSelectedVideoId] = useState<number | null>(null);

  const [page, setPage] = useState(1);
  const [data, setData] = useState<VideosResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadVideos() {
      setLoading(true);
      setError("");
      setData(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: "25",
      });

      if (filters.start) {
        params.set("start_date", filters.start);
      }

      if (filters.end) {
        params.set("end_date", filters.end);
      }

      const apiUrl =
        process.env.NEXT_PUBLIC_FSI_API_URL ||
        "http://127.0.0.1:8000";

      try {
        const response = await fetch(
          `${apiUrl}/api/clubs/${clubId}/videos?${params}`,
          {
            signal: controller.signal,
            cache: "no-store",
          }
        );

        if (!response.ok) {
          throw new Error(
            `Błąd API: ${response.status}`
          );
        }

        const result: VideosResponse =
          await response.json();

        if (!controller.signal.aborted) {
          setData(result);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Nie udało się pobrać filmów."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadVideos();

    return () => controller.abort();
  }, [clubId, filters, page]);

  function applyFilters() {
    setSelectedVideoId(null);
    if (start && end && start > end) {
      setError(
        "Data początkowa nie może być późniejsza niż końcowa."
      );
      return;
    }

    setPage(1);
    setFilters({ start, end });
  }

  function resetFilters() {
    setSelectedVideoId(null);
    setStart("");
    setEnd("");
    setPage(1);
    setFilters({ start: "", end: "" });
  }

  const videos = data?.items || [];

  // Wykres dotyczy filmów widocznych
  // na aktualnej stronie tabeli.
  const topVideos = [...videos]
    .filter(
      (video): video is Video & { views_count: number } =>
        video.views_count !== null
    )
    .sort((a, b) => b.views_count - a.views_count)
    .slice(0, 8);

  const maxViews = Math.max(
    1,
    ...topVideos.map((video) => video.views_count)
  );

  const totalPages = data
    ? Math.max(1, Math.ceil(data.total / data.page_size))
    : 1;

  return (
    <section className="mt-10 space-y-6">
      <div>
        <p className="text-xs font-semibold tracking-widest text-emerald-400">
          CONTENT PERFORMANCE
        </p>
        <h2 className="mt-2 text-2xl font-semibold">
          Video Analytics
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Statystyki ostatnich dostępnych odczytów filmów TikTok.
        </p>
      </div>

      {/* Filtry okresu publikacji */}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-white/10 bg-[#111923] p-5">
        <label className="flex flex-col gap-2 text-sm text-slate-400">
          Data publikacji od
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="rounded-lg border border-white/10 bg-[#090d12] px-3 py-2 text-white"
          />
        </label>

        <label className="flex flex-col gap-2 text-sm text-slate-400">
          Data publikacji do
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="rounded-lg border border-white/10 bg-[#090d12] px-3 py-2 text-white"
          />
        </label>

        <button
          onClick={applyFilters}
          className="rounded-lg bg-emerald-500 px-5 py-2 font-semibold text-black hover:bg-emerald-400"
        >
          Filtruj
        </button>

        <button
          onClick={resetFilters}
          className="rounded-lg border border-white/10 px-5 py-2 text-slate-300 hover:bg-white/5"
        >
          Wyczyść
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">
          {error}
        </div>
      )}

      {loading && (
        <div className="rounded-xl border border-white/10 p-8 text-slate-400">
          Wczytywanie statystyk filmów...
        </div>
      )}

      {!loading && data && (
        <>
          {/* Podsumowanie całego filtrowanego okresu */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Metric
              label="Liczba filmów"
              value={data.summary.videos}
            />
            <Metric
              label="Wyświetlenia"
              value={data.summary.views}
            />
            <Metric
              label="Polubienia"
              value={data.summary.likes}
            />
            <Metric
              label="Średnie wyświetlenia"
              value={
                data.summary.average_views === null
                  ? null
                  : Math.round(data.summary.average_views)
              }
            />
          </div>

          <p className="text-xs text-slate-500">
            Dane o wyświetleniach dostępne dla{" "}
            {data.summary.videos_with_views} z{" "}
            {data.summary.videos} filmów. Sumy obejmują
            tylko dostępne liczniki, nie brakujące wartości.
          </p>

          {/* Wykres top filmów */}
          <div className="rounded-xl border border-white/10 bg-[#111923] p-6">
            <h3 className="mb-2 text-lg font-semibold">
              Najpopularniejsze filmy
            </h3>
            <p className="mb-6 text-xs text-slate-500">
              Top 8 z bieżącej strony tabeli
            </p>

            {topVideos.length === 0 ? (
              <p className="py-8 text-sm text-slate-500">
                Brak filmów ze statystykami.
              </p>
            ) : (
              <div className="space-y-4">
                {topVideos.map((video) => (
                  <div key={video.id}>
                    <div className="mb-2 flex justify-between gap-3 text-sm">
                      <a
                        href={video.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-300 hover:text-emerald-400"
                      >
                        Film {video.tiktok_video_id.slice(-8)} ↗
                      </a>

                      <span className="font-semibold">
                        {formatNumber(video.views_count)}
                      </span>
                    </div>

                    <div className="h-3 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-emerald-400"
                        style={{
                          width: `${
                            (video.views_count / maxViews) * 100
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Tabela filmów */}
          <div className="overflow-hidden rounded-xl border border-white/10 bg-[#111923]">
            <div className="border-b border-white/10 p-5">
              <h3 className="font-semibold">
                Lista materiałów
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                Znaleziono {data.total} filmów
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Film</th>
                    <th className="px-4 py-3">Publikacja</th>
                    <th className="px-4 py-3">Wyświetlenia</th>
                    <th className="px-4 py-3">Polubienia</th>
                    <th className="px-4 py-3">Komentarze</th>
                    <th className="px-4 py-3">Udostępnienia</th>
                    <th className="px-4 py-3">Analiza</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-white/5">
                  {videos.map((video) => (
                    <tr
                      key={video.id}
                      className="hover:bg-white/[0.03]"
                    >
                      <td className="px-4 py-4">
                        <a
                          href={video.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-emerald-400 hover:underline"
                        >
                          {video.description
                            ? video.description.slice(0, 45)
                            : `Film ${video.tiktok_video_id.slice(-8)}`}
                          ↗
                        </a>
                      </td>

                      <td className="px-4 py-4 text-slate-400">
                        {video.published_at
                          ? video.published_at.slice(0, 10)
                          : "Brak daty"}
                      </td>

                      <td className="px-4 py-4">
                        {formatNumber(video.views_count)}
                      </td>

                      <td className="px-4 py-4">
                        {formatNumber(video.likes_count)}
                      </td>

                      <td className="px-4 py-4">
                        {formatNumber(video.comments_count)}
                      </td>

                      <td className="px-4 py-4">
                        {formatNumber(video.shares_count)}
                      </td>
                      <td className="px-4 py-4">
                        <button
                          onClick={() =>
                            setSelectedVideoId(video.id)
                          }
                          className="rounded-lg border border-emerald-500/30 px-3 py-2 text-sm font-medium text-emerald-400 hover:bg-emerald-500/10"
                        >
                          Historia
                        </button>
                      </td>
                    </tr>
                  ))}

                  {videos.length === 0 && (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-4 py-10 text-center text-slate-500"
                      >
                        Brak zapisanych filmów z wybranego okresu.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
            {selectedVideoId !== null && (
                <VideoHistory
                key={selectedVideoId}
                clubId={clubId}
                videoId={selectedVideoId}
                onClose={() => setSelectedVideoId(null)}
                />
            )}
          {/* Paginacja */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">
              Strona {page} z {totalPages}
            </span>

            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() =>
                  setPage((current) => Math.max(1, current - 1))
                }
                className="rounded-lg border border-white/10 px-4 py-2 text-sm disabled:opacity-30"
              >
                Poprzednia
              </button>

              <button
                disabled={page >= totalPages}
                onClick={() => setPage((current) => current + 1)}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm disabled:opacity-30"
              >
                Następna
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
