
"use client";

import { useEffect, useState } from "react";

type Snapshot = {
  id: number;
  views_count: number | null;
  likes_count: number | null;
  comments_count: number | null;
  shares_count: number | null;
  collected_at: string;
};

type VideoInfo = {
  id: number;
  club_id: number;
  club_name: string | null;
  tiktok_video_id: string;
  url: string;
  description: string | null;
  published_at: string | null;
};

type HistoryResponse = {
  video: VideoInfo;
  latest: Snapshot | null;
  views_growth: number | null;
  measurements_count: number;
  history: Snapshot[];
};

const numberFormat = new Intl.NumberFormat("pl-PL");

const dateFormat = new Intl.DateTimeFormat("pl-PL", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Europe/Warsaw",
});

function formatNumber(value: number | null) {
  return value === null ? "—" : numberFormat.format(value);
}

function formatDate(value: string | null) {
  if (!value) return "Brak danych";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "Brak danych"
    : dateFormat.format(date);
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0c131d] p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">
        {value}
      </p>
    </div>
  );
}

function ViewsChart({
  history,
}: {
  history: Snapshot[];
}) {
  const points = history
    .filter(
      (
        snapshot
      ): snapshot is Snapshot & {
        views_count: number;
      } => snapshot.views_count !== null
    )
    .map((snapshot) => ({
      ...snapshot,
      time: new Date(snapshot.collected_at).getTime(),
    }))
    .filter((snapshot) => Number.isFinite(snapshot.time));

  if (points.length < 2) {
    return (
      <div className="flex min-h-48 items-center justify-center rounded-lg border border-dashed border-white/10 px-4 text-center text-sm text-slate-400">
        Potrzebujemy co najmniej dwóch pomiarów
        wyświetleń, żeby narysować wykres.
      </div>
    );
  }

  const width = 800;
  const height = 280;

  const left = 85;
  const right = 20;
  const top = 25;
  const bottom = 45;

  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  const values = points.map((point) => point.views_count);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);

  // Dodajemy niewielki margines nad i pod linią.
  const paddingY = Math.max(1, (maximum - minimum) * 0.1);

  const minY = Math.max(0, minimum - paddingY);
  const maxY = maximum + paddingY;
  const rangeY = maxY - minY || 1;

  const minTime = Math.min(...points.map((p) => p.time));
  const maxTime = Math.max(...points.map((p) => p.time));
  const rangeTime = maxTime - minTime;

  const coordinates = points.map((point, index) => {
    const fractionX =
      rangeTime === 0
        ? index / (points.length - 1)
        : (point.time - minTime) / rangeTime;

    return {
      x: left + fractionX * plotWidth,
      y:
        top +
        (1 - (point.views_count - minY) / rangeY) *
          plotHeight,
    };
  });

  const path = coordinates
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`
    )
    .join(" ");

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="min-w-[480px] w-full"
          role="img"
          aria-label="Wykres historii wyświetleń filmu TikTok"
        >
          {/* Linie i etykiety osi Y */}
          {[0, 1, 2, 3, 4].map((step) => {
            const fraction = step / 4;
            const y = top + fraction * plotHeight;
            const value = maxY - fraction * rangeY;

            return (
              <g key={step}>
                <line
                  x1={left}
                  x2={width - right}
                  y1={y}
                  y2={y}
                  stroke="#334155"
                  strokeDasharray="4 6"
                />

                <text
                  x={left - 12}
                  y={y + 4}
                  textAnchor="end"
                  fontSize="12"
                  fill="#94a3b8"
                >
                  {numberFormat.format(Math.round(value))}
                </text>
              </g>
            );
          })}

          {/* Linia wyświetleń */}
          <path
            d={path}
            fill="none"
            stroke="#34d399"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Punkty pomiarowe */}
          {coordinates.map((point, index) => (
            <circle
              key={points[index].id}
              cx={point.x}
              cy={point.y}
              r="5"
              fill="#34d399"
              stroke="#0c131d"
              strokeWidth="2"
            >
              <title>
                {formatDate(points[index].collected_at)}
                {" – "}
                {formatNumber(points[index].views_count)}
                {" wyświetleń"}
              </title>
            </circle>
          ))}
        </svg>
      </div>

      <div className="flex justify-between gap-4 text-xs text-slate-500">
        <span>{formatDate(points[0].collected_at)}</span>
        <span>
          {formatDate(points[points.length - 1].collected_at)}
        </span>
      </div>

      <p className="text-xs text-slate-500">
        Najedź kursorem na punkt, aby zobaczyć wartość
        i datę pomiaru. Odstępy na osi poziomej
        odpowiadają czasowi odczytu.
      </p>
    </div>
  );
}

export default function VideoHistory({
  videoId,
  onClose,
}: {
  videoId: number;
  onClose: () => void;
}) {
  const [data, setData] = useState<HistoryResponse | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadHistory() {
      setLoading(true);
      setData(null);
      setError("");

      const apiUrl =
        process.env.NEXT_PUBLIC_FSI_API_URL ||
        "http://127.0.0.1:8000";

      try {
        const response = await fetch(
          `${apiUrl}/api/videos/${videoId}/history`,
          {
            cache: "no-store",
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          throw new Error(
            `Nie udało się pobrać historii. HTTP ${response.status}`
          );
        }

        const result: HistoryResponse =
          await response.json();

        if (!controller.signal.aborted) {
          setData(result);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Nieznany błąd."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadHistory();

    return () => controller.abort();
  }, [videoId]);

  const latest = data?.latest;

  const growth = data?.views_growth;

  const growthLabel =
    growth === null || growth === undefined
      ? "—"
      : `${growth > 0 ? "+" : ""}${numberFormat.format(growth)}`;

  return (
    <section className="rounded-2xl border border-emerald-500/20 bg-[#111923] p-5 md:p-7">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">
            Football Social Intelligence
          </p>
          <h3 className="mt-2 text-xl font-semibold text-white">
            Historia wyników filmu
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            Film w bazie: #{videoId}
          </p>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-white/10 px-4 py-2 text-sm text-slate-300 hover:bg-white/10"
        >
          Zamknij
        </button>
      </div>

      {loading && (
        <p className="text-sm text-slate-400">
          Pobieranie historii filmu...
        </p>
      )}

      {error && (
        <p className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </p>
      )}

      {!loading && data && (
        <div className="space-y-6">
          <div className="space-y-2">
            <p className="text-sm text-slate-300">
              {data.video.description ||
                `Film TikTok ${data.video.tiktok_video_id}`}
            </p>

            <a
              href={data.video.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-sm text-emerald-400 hover:underline"
            >
              Otwórz film na TikToku ↗
            </a>

            <p className="text-xs text-slate-500">
              Opublikowano:{" "}
              {formatDate(data.video.published_at)}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              label="Wyświetlenia"
              value={formatNumber(latest?.views_count ?? null)}
            />
            <StatCard
              label="Przyrost wyświetleń"
              value={growthLabel}
            />
            <StatCard
              label="Polubienia"
              value={formatNumber(latest?.likes_count ?? null)}
            />
            <StatCard
              label="Komentarze"
              value={formatNumber(latest?.comments_count ?? null)}
            />
            <StatCard
              label="Udostępnienia"
              value={formatNumber(latest?.shares_count ?? null)}
            />
            <StatCard
              label="Liczba pomiarów"
              value={numberFormat.format(
                data.measurements_count
              )}
            />
          </div>

          <div className="rounded-xl border border-white/10 bg-[#0c131d] p-5">
            <h4 className="mb-2 text-lg font-semibold text-white">
              Historia wyświetleń
            </h4>

            <p className="mb-5 text-sm text-slate-400">
              Zmiana liczby wyświetleń pomiędzy odczytami.
            </p>

            <ViewsChart history={data.history} />
          </div>

          <div className="overflow-hidden rounded-xl border border-white/10">
            <div className="border-b border-white/10 p-4">
              <h4 className="font-semibold">
                Zapisane pomiary
              </h4>
              <p className="mt-1 text-xs text-slate-500">
                Ostatni pomiar:{" "}
                {formatDate(latest?.collected_at ?? null)}
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Data odczytu</th>
                    <th className="px-4 py-3">Wyświetlenia</th>
                    <th className="px-4 py-3">Polubienia</th>
                    <th className="px-4 py-3">Komentarze</th>
                    <th className="px-4 py-3">Udostępnienia</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-white/5">
                  {data.history.map((snapshot) => (
                    <tr key={snapshot.id}>
                      <td className="px-4 py-3 text-slate-400">
                        {formatDate(snapshot.collected_at)}
                      </td>
                      <td className="px-4 py-3">
                        {formatNumber(snapshot.views_count)}
                      </td>
                      <td className="px-4 py-3">
                        {formatNumber(snapshot.likes_count)}
                      </td>
                      <td className="px-4 py-3">
                        {formatNumber(snapshot.comments_count)}
                      </td>
                      <td className="px-4 py-3">
                        {formatNumber(snapshot.shares_count)}
                      </td>
                    </tr>
                  ))}

                  {data.history.length === 0 && (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-4 py-8 text-center text-slate-500"
                      >
                        Brak zapisanych pomiarów.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
