
"use client";

import { useEffect, useState } from "react";

type CollectionStatus = "recent" | "stale" | "missing";

type ClubMonitoring = {
  club_id: number;
  name: string;
  tiktok_handle: string;

  followers_status: CollectionStatus;
  followers_last_at: string | null;
  followers_measurements: number;

  videos_status: CollectionStatus;
  videos_last_at: string | null;
  known_videos: number;
  measured_videos: number;
  video_measurements: number;
};

type Summary = {
  active_clubs: number;
  followers_recent: number;
  followers_stale: number;
  followers_missing: number;
  videos_recent: number;
  videos_stale: number;
  videos_missing: number;
  known_videos_total: number;
  video_measurements_total: number;
};

type LogFile = {
  name: string;
  exists: boolean;
  updated_at: string | null;
  read_error: boolean;
};

type LogEvent = {
  source: string;
  time_local: string;
  level: "ERROR" | "WARNING";
  message: string;
};

type MonitoringResponse = {
  generated_at: string;
  threshold_hours: number;
  summary: Summary;
  clubs: ClubMonitoring[];
  logs: {
    files: LogFile[];
    recent_events: LogEvent[];
  };
};

const numberFormat = new Intl.NumberFormat("pl-PL");

const dateFormat = new Intl.DateTimeFormat("pl-PL", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Europe/Warsaw",
});

function formatNumber(value: number) {
  return numberFormat.format(value);
}

function formatDate(value: string | null) {
  if (!value) {
    return "Brak danych";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Nieznana data";
  }

  return dateFormat.format(date);
}

function StatusBadge({
  status,
}: {
  status: CollectionStatus;
}) {
  const styles = {
    recent:
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
    stale:
      "border-amber-500/30 bg-amber-500/10 text-amber-400",
    missing:
      "border-slate-500/30 bg-slate-500/10 text-slate-400",
  };

  const labels = {
    recent: "Aktualne",
    stale: "Opóźnione",
    missing: "Brak danych",
  };

  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}

function MetricCard({
  label,
  value,
  description,
}: {
  label: string;
  value: number;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
      <p className="text-sm text-slate-400">
        {label}
      </p>

      <p className="mt-3 text-3xl font-semibold text-white">
        {formatNumber(value)}
      </p>

      <p className="mt-2 text-xs text-slate-500">
        {description}
      </p>
    </div>
  );
}

export default function CollectionMonitoringPage() {
  const [data, setData] =
    useState<MonitoringResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [hours, setHours] = useState(48);
  const [search, setSearch] = useState("");
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Automatyczne odświeżanie co 60 sekund.
  useEffect(() => {
    const interval = window.setInterval(() => {
      setRefreshKey((previous) => previous + 1);
    }, 60_000);

    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadMonitoring() {
      setLoading(true);
      setError("");

      const apiUrl =
        process.env.NEXT_PUBLIC_FSI_API_URL ||
        "http://127.0.0.1:8000";

      try {
        const response = await fetch(
          `${apiUrl}/api/monitoring/overview?hours=${hours}`,
          {
            signal: controller.signal,
            cache: "no-store",
          }
        );

        if (!response.ok) {
          throw new Error(
            `Nie udało się pobrać monitoringu. HTTP ${response.status}`
          );
        }

        const result: MonitoringResponse =
          await response.json();

        if (!controller.signal.aborted) {
          setData(result);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setData(null);
          setError(
            err instanceof Error
              ? err.message
              : "Nieznany błąd API."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadMonitoring();

    return () => controller.abort();
  }, [hours, refreshKey]);

  const filteredClubs = (data?.clubs ?? []).filter(
    (club) => {
      const query = search.trim().toLowerCase();

      const matchesSearch =
        club.name.toLowerCase().includes(query) ||
        club.tiktok_handle.toLowerCase().includes(query);

      // Brak filmów w bazie sam w sobie nie oznacza
      // awarii kolektora.
      const needsAttention =
        club.followers_status !== "recent" ||
        (
          club.known_videos > 0 &&
          club.videos_status !== "recent"
        );

      return (
        matchesSearch &&
        (!onlyProblems || needsAttention)
      );
    }
  );

  return (
    <main className="min-h-screen bg-[#090d12] px-5 py-10 text-white">
      <div className="mx-auto max-w-7xl space-y-8">
        {/* Nagłówek */}
        <header className="space-y-3">
          <a
            href="/panel/kluby"
            className="text-sm text-emerald-400 hover:underline"
          >
            ← Powrót do klubów
          </a>

          <p className="text-xs font-semibold tracking-[0.25em] text-emerald-400">
            FOOTBALL SOCIAL INTELLIGENCE
          </p>

          <h1 className="text-3xl font-bold md:text-4xl">
            Collection Monitoring
          </h1>

          <p className="max-w-3xl text-sm text-slate-400">
            Monitorowanie aktualności danych TikTok,
            liczby zapisanych pomiarów i komunikatów
            z automatycznych kolektorów.
          </p>
        </header>

        {/* Sterowanie */}
        <div className="flex flex-wrap items-end gap-4 rounded-xl border border-white/10 bg-[#111923] p-5">
          <label className="flex flex-col gap-2 text-sm text-slate-400">
            Próg aktualności danych
            <select
              value={hours}
              onChange={(event) =>
                setHours(Number(event.target.value))
              }
              className="rounded-lg border border-white/10 bg-[#090d12] px-3 py-2 text-white"
            >
              <option value={24}>24 godziny</option>
              <option value={48}>48 godzin</option>
              <option value={72}>72 godziny</option>
              <option value={168}>7 dni</option>
            </select>
          </label>

          <button
            type="button"
            onClick={() =>
              setRefreshKey((previous) => previous + 1)
            }
            disabled={loading}
            className="rounded-lg bg-emerald-500 px-5 py-2 font-semibold text-black hover:bg-emerald-400 disabled:opacity-50"
          >
            {loading ? "Odświeżanie..." : "Odśwież dane"}
          </button>

          {data && (
            <p className="text-xs text-slate-500">
              Ostatni odczyt: {formatDate(data.generated_at)}
            </p>
          )}
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5 text-sm text-red-300">
            {error}
            <p className="mt-2">
              Sprawdź, czy MySQL i FastAPI są uruchomione.
            </p>
          </div>
        )}

        {loading && !data && (
          <div className="rounded-xl border border-white/10 p-8 text-sm text-slate-400">
            Pobieranie informacji o kolektorach...
          </div>
        )}

        {data && (
          <>
            {/* Główne statystyki */}
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Aktywne kluby"
                value={data.summary.active_clubs}
                description="Zarejestrowane w MySQL"
              />

              <MetricCard
                label="Aktualne pomiary profili"
                value={data.summary.followers_recent}
                description={`Ostatni odczyt w ciągu ${hours} godzin`}
              />

              <MetricCard
                label="Aktualne pomiary filmów"
                value={data.summary.videos_recent}
                description="Liczba klubów ze świeżymi odczytami filmów"
              />

              <MetricCard
                label="Znane filmy"
                value={data.summary.known_videos_total}
                description="Łączna liczba filmów zapisanych w bazie"
              />
            </div>

            {/* Wyszukiwanie */}
            <div className="rounded-xl border border-white/10 bg-[#111923] p-5">
              <div className="flex flex-wrap items-center gap-4">
                <input
                  type="search"
                  value={search}
                  onChange={(event) =>
                    setSearch(event.target.value)
                  }
                  placeholder="Szukaj klubu lub @handle..."
                  className="min-w-0 flex-1 rounded-lg border border-white/10 bg-[#090d12] px-4 py-3 text-sm text-white outline-none focus:border-emerald-500"
                />

                <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={onlyProblems}
                    onChange={(event) =>
                      setOnlyProblems(event.target.checked)
                    }
                    className="accent-emerald-500"
                  />
                  Wymagające uwagi
                </label>
              </div>

              <p className="mt-3 text-xs text-slate-500">
                Wyświetlono {filteredClubs.length} z{" "}
                {data.clubs.length} aktywnych klubów.
              </p>
            </div>

            {/* Monitoring klubów */}
            <section className="overflow-hidden rounded-xl border border-white/10 bg-[#111923]">
              <div className="border-b border-white/10 p-5">
                <h2 className="text-lg font-semibold">
                  Status zbierania danych
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Ostatnie poprawne odczyty dostępne w MySQL
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/5 text-slate-400">
                    <tr>
                      <th className="px-4 py-4">Klub</th>
                      <th className="px-4 py-4">Obserwujący</th>
                      <th className="px-4 py-4">Ostatni profil</th>
                      <th className="px-4 py-4">Filmy</th>
                      <th className="px-4 py-4">Ostatni film</th>
                      <th className="px-4 py-4">Pomiary</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-white/5">
                    {filteredClubs.map((club) => (
                      <tr
                        key={club.club_id}
                        className="hover:bg-white/[0.03]"
                      >
                        <td className="px-4 py-4">
                          <a
                            href={`/panel/kluby/${club.club_id}`}
                            className="font-medium text-white hover:text-emerald-400"
                          >
                            {club.name}
                          </a>
                          <p className="mt-1 text-xs text-slate-500">
                            @{club.tiktok_handle}
                          </p>
                        </td>

                        <td className="px-4 py-4">
                          <StatusBadge
                            status={club.followers_status}
                          />
                          <p className="mt-2 text-xs text-slate-500">
                            {formatNumber(
                              club.followers_measurements
                            )} pomiarów
                          </p>
                        </td>

                        <td className="px-4 py-4 text-slate-400">
                          {formatDate(club.followers_last_at)}
                        </td>

                        <td className="px-4 py-4">
                          <StatusBadge
                            status={club.videos_status}
                          />
                          <p className="mt-2 text-xs text-slate-500">
                            {club.measured_videos} /{" "}
                            {club.known_videos} filmów z pomiarami
                          </p>
                        </td>

                        <td className="px-4 py-4 text-slate-400">
                          {formatDate(club.videos_last_at)}
                        </td>

                        <td className="px-4 py-4">
                          {formatNumber(
                            club.video_measurements
                          )}
                        </td>
                      </tr>
                    ))}

                    {filteredClubs.length === 0 && (
                      <tr>
                        <td
                          colSpan={6}
                          className="px-4 py-12 text-center text-slate-500"
                        >
                          Brak klubów spełniających filtry.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Status logów */}
            <section className="rounded-xl border border-white/10 bg-[#111923] p-6">
              <h2 className="text-lg font-semibold">
                Pliki logów automatyzacji
              </h2>

              <p className="mt-2 text-sm text-slate-400">
                Ostatnia modyfikacja pliku oznacza,
                że zapisano do niego informacje,
                ale nie gwarantuje powodzenia zadania.
              </p>

              <div className="mt-5 grid gap-3 md:grid-cols-3">
                {data.logs.files.map((log) => (
                  <div
                    key={log.name}
                    className="rounded-lg border border-white/10 bg-[#0c131d] p-4"
                  >
                    <p className="break-all text-sm font-semibold">
                      {log.name}
                    </p>

                    <p className="mt-2 text-xs text-slate-400">
                      {!log.exists
                        ? "Plik jeszcze nie istnieje"
                        : log.read_error
                          ? "Nie można odczytać logu"
                          : `Aktualizacja: ${formatDate(
                              log.updated_at
                            )}`}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* Ostrzeżenia i błędy */}
            <section className="overflow-hidden rounded-xl border border-white/10 bg-[#111923]">
              <div className="border-b border-white/10 p-5">
                <h2 className="text-lg font-semibold">
                  Ostatnie ostrzeżenia i błędy
                </h2>

                <p className="mt-1 text-xs text-slate-500">
                  Komunikaty z końcowych fragmentów logów.
                  Daty wpisów pochodzą z czasu lokalnego komputera.
                </p>
              </div>

              {data.logs.recent_events.length === 0 ? (
                <p className="p-6 text-sm text-slate-400">
                  Brak ostrzeżeń i błędów w odczytanych
                  fragmentach logów.
                </p>
              ) : (
                <div className="divide-y divide-white/5">
                  {data.logs.recent_events.map(
                    (event, index) => (
                      <div
                        key={`${event.source}-${event.time_local}-${index}`}
                        className="p-5"
                      >
                        <div className="mb-2 flex flex-wrap items-center gap-3">
                          <span
                            className={`text-xs font-bold ${
                              event.level === "ERROR"
                                ? "text-red-400"
                                : "text-amber-400"
                            }`}
                          >
                            {event.level}
                          </span>

                          <span className="text-xs text-slate-500">
                            {event.time_local}
                          </span>

                          <span className="text-xs text-slate-500">
                            {event.source}
                          </span>
                        </div>

                        <p className="break-words text-sm text-slate-300">
                          {event.message}
                        </p>
                      </div>
                    )
                  )}
                </div>
              )}
            </section>

            <p className="text-xs text-slate-500">
              Monitoring odświeża się automatycznie
              co 60 sekund. Statusy oznaczają świeżość
              zapisanych danych, a nie bieżący stan
              procesu Windows Task Scheduler.
            </p>
          </>
        )}
      </div>
    </main>
  );
}
