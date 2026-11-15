
"use client";

import { useEffect, useState } from "react";

type JobStatus =
  | "queued"
  | "running"
  | "cancel_requested"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled"
  | "interrupted";

type Job = {
  id: number;
  status: JobStatus;
  start_date: string;
  end_date: string;
  total_clubs: number;
  completed_clubs: number;
  new_videos: number;
  refreshed_videos: number;
  followers_saved: number;
  errors_count: number;
  message: string | null;
  created_at: string | null;
  started_at: string | null;
  heartbeat_at: string | null;
  finished_at: string | null;
};

type ClubResult = {
  id: number;
  club_id: number;
  club_name: string;
  status: string;
  new_videos: number;
  refreshed_videos: number;
  followers_saved: number;
  errors_count: number;
  started_at: string | null;
  finished_at: string | null;
  message: string | null;
};

type JobDetails = {
  job: Job;
  worker_state: string;
  clubs: ClubResult[];
};

const API =
  process.env.NEXT_PUBLIC_FSI_API_URL ||
  "http://127.0.0.1:8000";

const BASE = `${API}/api/web-collection/management`;

const numberFormat = new Intl.NumberFormat("pl-PL");

const dateFormat = new Intl.DateTimeFormat("pl-PL", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Europe/Warsaw",
});

const labels: Record<JobStatus, string> = {
  queued: "W kolejce",
  running: "W trakcie",
  cancel_requested: "Anulowanie...",
  completed: "Zakończone",
  partial: "Zakończone z błędami",
  failed: "Błąd",
  cancelled: "Anulowane",
  interrupted: "Przerwane",
};

function formatDate(value: string | null) {
  if (!value) return "—";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "—"
    : dateFormat.format(date);
}

function Status({
  status,
}: {
  status: string;
}) {
  let colors = "border-slate-500/30 text-slate-400";

  if (status === "completed") {
    colors = "border-emerald-500/30 text-emerald-400";
  } else if (
    status === "partial" ||
    status === "cancel_requested"
  ) {
    colors = "border-amber-500/30 text-amber-400";
  } else if (
    status === "failed" ||
    status === "interrupted"
  ) {
    colors = "border-red-500/30 text-red-400";
  } else if (status === "running") {
    colors = "border-sky-500/30 text-sky-400";
  }

  const text = labels[status as JobStatus] ?? status;

  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${colors}`}
    >
      {text}
    </span>
  );
}

function Metric({
  title,
  value,
}: {
  title: string;
  value: number;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0c131d] p-4">
      <p className="text-sm text-slate-400">
        {title}
      </p>
      <p className="mt-2 text-2xl font-semibold">
        {numberFormat.format(value)}
      </p>
    </div>
  );
}

export default function CollectionJobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] =
    useState<number | null>(null);

  const [details, setDetails] =
    useState<JobDetails | null>(null);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  // Pobieramy historię i szczegóły co 5 sekund.
  useEffect(() => {
    let active = true;

    async function loadJobs() {
      try {
        const response = await fetch(
          `${BASE}/jobs?limit=30`,
          { cache: "no-store" }
        );

        if (!response.ok) {
          throw new Error(
            `Błąd pobierania historii: HTTP ${response.status}`
          );
        }

        const result: { items: Job[] } =
          await response.json();

        if (!active) return;

        setJobs(result.items);
        setError("");

        if (selectedId === null && result.items.length > 0) {
          setSelectedId(result.items[0].id);
        }

        if (selectedId !== null) {
          const detailsResponse = await fetch(
            `${BASE}/jobs/${selectedId}`,
            { cache: "no-store" }
          );

          if (!detailsResponse.ok) {
            throw new Error(
              `Błąd szczegółów: HTTP ${detailsResponse.status}`
            );
          }

          const detailsData: JobDetails =
            await detailsResponse.json();

          if (active) {
            setDetails(detailsData);
          }
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Nie udało się pobrać zadań."
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadJobs();

    const interval = window.setInterval(() => {
      void loadJobs();
    }, 5000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [selectedId, refreshKey]);

  async function sendAction(
    action: "cancel" | "recover"
  ) {
    if (selectedId === null || busy) return;

    const question =
      action === "cancel"
        ? "Zlecić bezpieczne anulowanie tego zadania?"
        : "Odblokować kolejkę po potwierdzonej awarii procesu?";

    if (!window.confirm(question)) return;

    setBusy(true);
    setError("");
    setNotice("");

    try {
      const response = await fetch(
        `${BASE}/jobs/${selectedId}/${action}`,
        { method: "POST" }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : `HTTP ${response.status}`
        );
      }

      setNotice(
        typeof result.message === "string"
          ? result.message
          : "Zapisano zmianę stanu zadania."
      );

      setRefreshKey((current) => current + 1);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Nie udało się wykonać operacji."
      );
    } finally {
      setBusy(false);
    }
  }

  const selected = details?.job;

  const isActive =
    selected?.status === "queued" ||
    selected?.status === "running";

  const canRecover =
    selected !== undefined &&
    (
      selected.status === "queued" ||
      selected.status === "running" ||
      selected.status === "cancel_requested"
    ) &&
    details?.worker_state === "absent";

  const progress =
    selected && selected.total_clubs > 0
      ? Math.round(
          selected.completed_clubs /
          selected.total_clubs * 100
        )
      : 0;

  return (
    <main className="min-h-screen bg-[#090d12] px-5 py-10 text-white">
      <div className="mx-auto max-w-7xl space-y-8">
        <header className="space-y-3">
          <a
            href="/panel/pobieranie"
            className="text-sm text-emerald-400 hover:underline"
          >
            ← Centrum pobierania
          </a>

          <p className="text-xs font-semibold tracking-[0.25em] text-emerald-400">
            FOOTBALL SOCIAL INTELLIGENCE
          </p>

          <h1 className="text-3xl font-bold">
            Collection Job Management
          </h1>

          <p className="text-sm text-slate-400">
            Historia pobierania danych TikTok,
            wyniki poszczególnych klubów oraz
            kontrolowane anulowanie zadań.
          </p>
        </header>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {notice && (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-300">
            {notice}
          </div>
        )}

        {loading && (
          <p className="text-sm text-slate-400">
            Wczytywanie historii...
          </p>
        )}

        <div className="flex justify-between gap-3">
          <p className="text-sm text-slate-400">
            Ostatnie 30 zadań. Odświeżanie co 5 sekund.
          </p>

          <button
            type="button"
            onClick={() =>
              setRefreshKey((current) => current + 1)
            }
            className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white hover:bg-white/10"
          >
            Odśwież
          </button>
        </div>

        {/* Historia wszystkich uruchomień */}
        <section className="overflow-hidden rounded-xl border border-white/10 bg-[#111923]">
          <div className="border-b border-white/10 p-5">
            <h2 className="text-lg font-semibold">
              Historia zadań
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-white/5 text-slate-400">
                <tr>
                  <th className="px-4 py-3">Zadanie</th>
                  <th className="px-4 py-3">Data uruchomienia</th>
                  <th className="px-4 py-3">Okres filmów</th>
                  <th className="px-4 py-3">Kluby</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-white/5">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => {
                      setSelectedId(job.id);
                      setDetails(null);
                      setNotice("");
                    }}
                    className={`cursor-pointer hover:bg-white/5 ${
                      selectedId === job.id
                        ? "bg-emerald-500/10"
                        : ""
                    }`}
                  >
                    <td className="px-4 py-4 font-semibold">
                      #{job.id}
                    </td>

                    <td className="px-4 py-4 text-slate-400">
                      {formatDate(job.created_at)}
                    </td>

                    <td className="px-4 py-4 text-slate-400">
                      {job.start_date} – {job.end_date}
                    </td>

                    <td className="px-4 py-4">
                      {job.completed_clubs}/{job.total_clubs}
                    </td>

                    <td className="px-4 py-4">
                      <Status status={job.status}/>
                    </td>
                  </tr>
                ))}

                {jobs.length === 0 && !loading && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-4 py-10 text-center text-slate-500"
                    >
                      Nie uruchomiono jeszcze żadnego zadania.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Szczegóły wybranego zadania */}
        {selected && (
          <section className="space-y-5 rounded-xl border border-white/10 bg-[#111923] p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">
                  Szczegóły zadania #{selected.id}
                </h2>
                <p className="mt-2 text-sm text-slate-400">
                  {selected.message}
                </p>
              </div>

              <Status status={selected.status}/>
            </div>

            <div className="h-3 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full bg-emerald-400 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>

            <p className="text-sm text-slate-400">
              Przetworzone kluby: {selected.completed_clubs}
              /{selected.total_clubs} ({progress}%)
            </p>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric
                title="Nowe filmy"
                value={selected.new_videos}
              />
              <Metric
                title="Odświeżone filmy"
                value={selected.refreshed_videos}
              />
              <Metric
                title="Pomiary obserwujących"
                value={selected.followers_saved}
              />
              <Metric
                title="Błędy"
                value={selected.errors_count}
              />
            </div>

            <div className="grid gap-2 text-sm text-slate-400 md:grid-cols-2">
              <p>
                Rozpoczęto: {formatDate(selected.started_at)}
              </p>
              <p>
                Zakończono: {formatDate(selected.finished_at)}
              </p>
              <p>
                Ostatnia aktywność:{" "}
                {formatDate(selected.heartbeat_at)}
              </p>
              <p>
                Proces:{" "}
                {details.worker_state === "alive"
                  ? "Działa"
                  : details.worker_state === "absent"
                    ? "Nie znaleziono"
                    : details.worker_state === "unknown"
                      ? "Nie można zweryfikować"
                      : "Zadanie zakończone"}
              </p>
            </div>

            {/* Bezpieczne sterowanie zadaniem */}
            <div className="flex flex-wrap gap-3 border-t border-white/10 pt-5">
              <button
                type="button"
                disabled={!isActive || busy}
                onClick={() => void sendAction("cancel")}
                className="rounded-lg border border-amber-500/40 px-5 py-3 text-sm font-medium text-amber-300 hover:bg-amber-500/10 disabled:cursor-not-allowed disabled:opacity-30"
              >
                Anuluj zadanie
              </button>

              <button
                type="button"
                disabled={!canRecover || busy}
                onClick={() => void sendAction("recover")}
                className="rounded-lg border border-red-500/40 px-5 py-3 text-sm font-medium text-red-300 hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-30"
              >
                Odzyskaj po awarii
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Anulowanie nie zatrzymuje siłowo procesu.
              Odzyskiwanie jest dostępne dopiero po
              potwierdzeniu, że worker nie działa,
              i sprawdzeniu czasu ostatniej aktywności.
            </p>
          </section>
        )}

        {/* Wyniki klubów */}
        {details && (
          <section className="overflow-hidden rounded-xl border border-white/10 bg-[#111923]">
            <div className="border-b border-white/10 p-5">
              <h2 className="text-lg font-semibold">
                Wyniki poszczególnych klubów
              </h2>

              <p className="mt-2 text-xs text-slate-500">
                Szczegółowe dane będą zapisywane dla
                zadań uruchomionych po aktualizacji FSI 0.8.6.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Klub</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Nowe filmy</th>
                    <th className="px-4 py-3">Odświeżone</th>
                    <th className="px-4 py-3">Obserwujący</th>
                    <th className="px-4 py-3">Błędy</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-white/5">
                  {details.clubs.map((club) => (
                    <tr key={club.id}>
                      <td className="px-4 py-4">
                        <a
                          href={`/panel/kluby/${club.club_id}`}
                          className="text-emerald-400 hover:underline"
                        >
                          {club.club_name}
                        </a>
                        <p className="mt-1 text-xs text-slate-500">
                          {club.message}
                        </p>
                      </td>

                      <td className="px-4 py-4">
                        <Status status={club.status}/>
                      </td>

                      <td className="px-4 py-4">
                        {numberFormat.format(club.new_videos)}
                      </td>

                      <td className="px-4 py-4">
                        {numberFormat.format(club.refreshed_videos)}
                      </td>

                      <td className="px-4 py-4">
                        {numberFormat.format(club.followers_saved)}
                      </td>

                      <td className="px-4 py-4">
                        {numberFormat.format(club.errors_count)}
                      </td>
                    </tr>
                  ))}

                  {details.clubs.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-10 text-center text-slate-500"
                      >
                        Brak szczegółowych wyników klubów
                        dla tego zadania.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <div className="flex flex-wrap gap-5 text-sm">
          <a
            href="/panel/pobieranie"
            className="text-emerald-400 hover:underline"
          >
            Centrum pobierania
          </a>

          <a
            href="/panel/monitoring"
            className="text-emerald-400 hover:underline"
          >
            Collection Monitoring
          </a>

          <a
            href="/panel/kluby"
            className="text-emerald-400 hover:underline"
          >
            Profile klubów
          </a>
        </div>
      </div>
    </main>
  );
}
