"use client";

import { useEffect, useState } from "react";

type EngagementVideo = {
  video_id: number;
  tiktok_video_id: string;
  url: string;
  description: string | null;
  published_at: string | null;
  collected_at: string;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  interactions: number;
  engagement_rate: number;
};

type EngagementResponse = {
  club_id: number;
  club_name: string;
  summary: {
    videos_total: number;
    videos_complete: number;
    videos_excluded: number;
    included_views: number;
    included_interactions: number;
    weighted_engagement_rate: number | null;
    average_engagement_rate: number | null;
  };
  minimum_views_for_ranking: number;
  top_videos: EngagementVideo[];
};

const numberFormat = new Intl.NumberFormat("pl-PL");
const percentFormat = new Intl.NumberFormat("pl-PL", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function percent(value: number | null) {
  return value === null ? "—" : `${percentFormat.format(value)}%`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0c131d] p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-emerald-400">{value}</p>
    </div>
  );
}

export default function EngagementAnalytics({
  clubId,
  startDate,
  endDate,
}: {
  clubId: number;
  startDate: string;
  endDate: string;
}) {
  const [data, setData] = useState<EngagementResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      setLoading(true);
      setError("");
      setData(null);

      const params = new URLSearchParams();
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);

      const apiUrl =
        process.env.NEXT_PUBLIC_FSI_API_URL || "http://127.0.0.1:8000";
      const query = params.toString();
      const url = `${apiUrl}/api/clubs/${clubId}/engagement${query ? `?${query}` : ""}`;

      try {
        const response = await fetch(url, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error(`Błąd API Engagement: HTTP ${response.status}`);
        }

        const result: EngagementResponse = await response.json();
        if (!controller.signal.aborted) setData(result);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error ? err.message : "Nie udało się pobrać danych."
          );
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    load();
    return () => controller.abort();
  }, [clubId, startDate, endDate]);

  const top = data?.top_videos ?? [];
  const maxRate = Math.max(1, ...top.map((video) => video.engagement_rate));

  return (
    <section className="space-y-5 rounded-xl border border-emerald-500/20 bg-[#111923] p-6">
      <div>
        <p className="text-xs font-semibold tracking-widest text-emerald-400">
          ENGAGEMENT ANALYTICS
        </p>
        <h3 className="mt-2 text-xl font-semibold text-white">
          Zaangażowanie odbiorców
        </h3>
        <p className="mt-2 text-sm text-slate-400">
          ER według wyświetleń = (polubienia + komentarze + udostępnienia)
          / wyświetlenia × 100%.
        </p>
      </div>

      {loading && <p className="text-sm text-slate-400">Liczenie wskaźników...</p>}
      {error && <p className="text-sm text-red-300">{error}</p>}

      {!loading && data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Stat
              label="Łączny ER (ważony wyświetleniami)"
              value={percent(data.summary.weighted_engagement_rate)}
            />
            <Stat
              label="Średni ER na film"
              value={percent(data.summary.average_engagement_rate)}
            />
            <Stat
              label="Interakcje (kompletne filmy)"
              value={numberFormat.format(data.summary.included_interactions)}
            />
            <Stat
              label="Filmy z kompletnymi danymi"
              value={`${data.summary.videos_complete} / ${data.summary.videos_total}`}
            />
          </div>

          <p className="text-xs leading-relaxed text-slate-400">
            Pominięto {data.summary.videos_excluded} filmów bez pełnego zestawu
            statystyk lub z zerową liczbą wyświetleń. Wyniki dotyczą ostatnich
            zapisanych liczników poszczególnych filmów, nie wyświetleń zdobytych
            w wybranym okresie. Wszystkie statystyki obejmują cały filtrowany
            okres publikacji, nie tylko aktualną stronę tabeli.
          </p>

          <div>
            <h4 className="mb-1 font-semibold text-white">
              Top 10 filmów według Engagement Rate
            </h4>
            <p className="mb-5 text-xs text-slate-400">
              Dla porównywalności ranking obejmuje materiały z co najmniej{" "}
              {numberFormat.format(data.minimum_views_for_ranking)} wyświetleniami.
            </p>

            {top.length === 0 ? (
              <p className="py-6 text-sm text-slate-500">
                Brak filmów spełniających warunki rankingu.
              </p>
            ) : (
              <div className="space-y-5">
                {top.map((video, index) => (
                  <div key={video.video_id} className="space-y-2">
                    <div className="flex items-start justify-between gap-4 text-sm">
                      <a
                        href={video.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="min-w-0 text-slate-200 hover:text-emerald-400"
                        title={video.description ?? undefined}
                      >
                        {index + 1}. {video.description
                          ? video.description.slice(0, 75)
                          : `Film ${video.tiktok_video_id.slice(-8)}`} ↗
                      </a>
                      <strong className="shrink-0 text-emerald-400">
                        {percent(video.engagement_rate)}
                      </strong>
                    </div>
                    <div className="h-2.5 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-emerald-400"
                        style={{ width: `${(video.engagement_rate / maxRate) * 100}%` }}
                      />
                    </div>
                    <p className="text-xs text-slate-500">
                      {numberFormat.format(video.views)} wyświetleń ·{" "}
                      {numberFormat.format(video.interactions)} interakcji
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
