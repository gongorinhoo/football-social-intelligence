"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type ClubRow = {
  club_id: number;
  club_name: string;
  tiktok_handle: string;
  videos_total: number;
  videos_with_views: number;
  videos_with_complete_er: number;
  total_views: number | null;
  average_views: number | null;
  weighted_er: number | null;
  eligible: boolean;
  rank: number | null;
};

type RankingResponse = {
  sort_by: "views" | "avg_views" | "er";
  min_videos: number;
  clubs_total: number;
  clubs_ranked: number;
  clubs: ClubRow[];
};

type SortBy = RankingResponse["sort_by"];

const numberFormatter = new Intl.NumberFormat("pl-PL", {
  maximumFractionDigits: 1,
});

function number(value: number | null) {
  return value === null ? "—" : numberFormatter.format(value);
}

function percent(value: number | null) {
  return value === null ? "—" : `${value.toFixed(2).replace(".", ",")}%`;
}

export default function ClubRankingsPage() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("avg_views");
  const [minVideos, setMinVideos] = useState(1);
  const [applied, setApplied] = useState({
    startDate: "",
    endDate: "",
    sortBy: "avg_views" as SortBy,
    minVideos: 1,
  });
  const [data, setData] = useState<RankingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadRankings() {
      setLoading(true);
      setError("");
      setData(null);
      const query = new URLSearchParams({
        sort_by: applied.sortBy,
        min_videos: String(applied.minVideos),
      });
      if (applied.startDate) query.set("start_date", applied.startDate);
      if (applied.endDate) query.set("end_date", applied.endDate);

      const apiUrl =
        process.env.NEXT_PUBLIC_FSI_API_URL || "http://127.0.0.1:8000";

      try {
        const response = await fetch(
          `${apiUrl}/api/rankings/clubs?${query.toString()}`,
          { cache: "no-store", signal: controller.signal }
        );
        if (!response.ok) throw new Error(`Błąd FastAPI: HTTP ${response.status}`);
        const result: RankingResponse = await response.json();
        if (!controller.signal.aborted) setData(result);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Błąd pobierania rankingu");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    loadRankings();
    return () => controller.abort();
  }, [applied]);

  function applyFilters() {
    if (startDate && endDate && startDate > endDate) {
      setError("Data początkowa jest późniejsza niż końcowa.");
      return;
    }
    setApplied({ startDate, endDate, sortBy, minVideos });
  }

  return (
    <main className="min-h-screen bg-[#080e14] px-4 py-10 text-white md:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <Link href="/panel/kluby" className="text-sm text-emerald-400 hover:underline">
          ← Wróć do klubów
        </Link>

        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-400">
            Football Social Intelligence
          </p>
          <h1 className="mt-2 text-3xl font-bold">Ranking klubów TikTok</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Porównanie zapisanych wyników filmów na podstawie najnowszego pomiaru
            każdego materiału. Okres dotyczy dat publikacji, nie dat zdobycia wyświetleń.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-4 rounded-xl border border-white/10 bg-[#111923] p-5">
          <label className="flex flex-col gap-2 text-sm text-slate-300">
            Publikacja od
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded-lg border border-white/10 bg-[#080e14] px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm text-slate-300">
            Publikacja do
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="rounded-lg border border-white/10 bg-[#080e14] px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm text-slate-300">
            Sortuj według
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortBy)}
              className="rounded-lg border border-white/10 bg-[#080e14] px-3 py-2"
            >
              <option value="avg_views">Średnie wyświetlenia</option>
              <option value="views">Łączne wyświetlenia</option>
              <option value="er">Ważony Engagement Rate</option>
            </select>
          </label>
          <label className="flex flex-col gap-2 text-sm text-slate-300">
            Min. filmów z danymi
            <select
              value={minVideos}
              onChange={(e) => setMinVideos(Number(e.target.value))}
              className="rounded-lg border border-white/10 bg-[#080e14] px-3 py-2"
            >
              <option value={1}>1 – test</option>
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
            </select>
          </label>
          <button
            type="button"
            onClick={applyFilters}
            className="rounded-lg bg-emerald-500 px-5 py-2 font-semibold text-black hover:bg-emerald-400"
          >
            Pokaż ranking
          </button>
        </div>

        {error && (
          <p role="alert" className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-300">
            {error}
          </p>
        )}

        {loading && <p className="text-sm text-slate-400">Wczytywanie rankingu...</p>}

        {!loading && data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
                <p className="text-sm text-slate-400">Kluby w rankingu</p>
                <p className="mt-2 text-3xl font-semibold text-emerald-400">
                  {data.clubs_ranked}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
                <p className="text-sm text-slate-400">Aktywne kluby w bazie</p>
                <p className="mt-2 text-3xl font-semibold">{data.clubs_total}</p>
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-white/10 bg-[#111923]">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[950px] text-left text-sm">
                  <thead className="bg-white/5 text-slate-400">
                    <tr>
                      <th className="px-4 py-3">Pozycja</th>
                      <th className="px-4 py-3">Klub</th>
                      <th className="px-4 py-3">Filmy / z wyświetleniami</th>
                      <th className="px-4 py-3">Suma wyświetleń</th>
                      <th className="px-4 py-3">Śr. wyświetlenia</th>
                      <th className="px-4 py-3">Ważony ER</th>
                      <th className="px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {data.clubs.map((club) => (
                      <tr key={club.club_id} className="hover:bg-white/[0.03]">
                        <td className="px-4 py-4 font-semibold text-emerald-400">
                          {club.rank ?? "—"}
                        </td>
                        <td className="px-4 py-4">
                          <Link
                            href={`/panel/kluby/${club.club_id}`}
                            className="font-medium text-white hover:text-emerald-400"
                          >
                            {club.club_name}
                          </Link>
                          <p className="text-xs text-slate-500">@{club.tiktok_handle}</p>
                        </td>
                        <td className="px-4 py-4 text-slate-300">
                          {club.videos_total} / {club.videos_with_views}
                        </td>
                        <td className="px-4 py-4">{number(club.total_views)}</td>
                        <td className="px-4 py-4">{number(club.average_views)}</td>
                        <td className="px-4 py-4">
                          {percent(club.weighted_er)}
                          <p className="text-xs text-slate-500">
                            Pełne metryki: {club.videos_with_complete_er}
                          </p>
                        </td>
                        <td className="px-4 py-4 text-xs">
                          {club.eligible ? (
                            <span className="text-emerald-400">W rankingu</span>
                          ) : (
                            <span className="text-amber-300">Za mało danych</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <p className="text-xs leading-relaxed text-slate-500">
              Ranking obejmuje jedynie dane, które zostały dotychczas zebrane.
              Nie oznacza pełnego zestawienia klubów w Polsce. Łączne i średnie
              wyświetlenia liczymy z filmów z dostępnym licznikiem. Ważony ER = suma
              (polubień + komentarzy + udostępnień) / suma wyświetleń × 100%,
              tylko dla filmów z kompletnymi danymi i dodatnimi wyświetleniami.
              Przy sortowaniu po ER próg minimalnej liczby filmów dotyczy filmów
              z kompletnymi metrykami.
            </p>
          </>
        )}
      </div>
    </main>
  );
}
