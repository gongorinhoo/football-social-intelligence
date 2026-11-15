
"use client";

import { useEffect, useState } from "react";

type Club = {
  id: number;
  name: string;
  handle: string;
};

type Job = {
  id: number;
  status: string;
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

const API =
  process.env.NEXT_PUBLIC_FSI_API_URL ||
  "http://127.0.0.1:8000";

const numberFormat = new Intl.NumberFormat("pl-PL");

function formatDate(value: string | null) {
  if (!value) return "—";

  return new Intl.DateTimeFormat("pl-PL", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Warsaw",
  }).format(new Date(value));
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#111923] p-4">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold">
        {numberFormat.format(value)}
      </p>
    </div>
  );
}

export default function WebCollectionPage() {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [scope, setScope] = useState<"selected" | "all">(
    "selected"
  );
  const [search, setSearch] = useState("");

  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const [discover, setDiscover] = useState(true);
  const [refresh, setRefresh] = useState(true);
  const [followers, setFollowers] = useState(false);

  const [maxScanned, setMaxScanned] = useState(150);
  const [maxDetails, setMaxDetails] = useState(20);
  const [maxNew, setMaxNew] = useState(5);
  const [maxExisting, setMaxExisting] = useState(5);

  const [job, setJob] = useState<Job | null>(null);
  const [starting, setStarting] = useState(false);
  const [loadingClubs, setLoadingClubs] = useState(true);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  // Ładujemy kluby z MySQL przez FastAPI.
  useEffect(() => {
    const controller = new AbortController();

    async function loadClubs() {
      try {
        const response = await fetch(
          `${API}/api/web-collection/clubs`,
          {
            cache: "no-store",
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`Błąd klubów: HTTP ${response.status}`);
        }

        const data: { items: Club[] } = await response.json();

        if (!controller.signal.aborted) {
          setClubs(data.items);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Nie można pobrać klubów."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoadingClubs(false);
        }
      }
    }

    void loadClubs();

    return () => controller.abort();
  }, []);

  // Status zadania sprawdzamy co 5 sekund.
  useEffect(() => {
    let active = true;

    async function loadLatest() {
      try {
        const response = await fetch(
          `${API}/api/web-collection/jobs/latest`,
          { cache: "no-store" }
        );

        if (!response.ok) return;

        const data: { job: Job | null } =
          await response.json();

        if (active) {
          setJob(data.job);
        }
      } catch {
        // Krótka niedostępność API nie usuwa
        // ostatniego widocznego stanu zadania.
      }
    }

    void loadLatest();

    const timer = window.setInterval(() => {
      void loadLatest();
    }, 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  function toggleClub(id: number) {
    setSelectedIds((previous) =>
      previous.includes(id)
        ? previous.filter((value) => value !== id)
        : [...previous, id]
    );
  }

  async function startCollection() {
    setError("");
    setInfo("");

    if (!start || !end || start > end) {
      setError("Wybierz poprawny zakres dat.");
      return;
    }

    if (
      scope === "selected" &&
      selectedIds.length === 0
    ) {
      setError("Wybierz przynajmniej jeden klub.");
      return;
    }

    if (!discover && !refresh && !followers) {
      setError("Wybierz co najmniej jeden rodzaj pobierania.");
      return;
    }

    const count =
      scope === "all" ? clubs.length : selectedIds.length;

    if (
      count > 10 &&
      !window.confirm(
        `Uruchomić pobieranie dla ${count} klubów? ` +
        "Ta operacja może wykonać wiele odczytów TikToka."
      )
    ) {
      return;
    }

    setStarting(true);

    try {
      const response = await fetch(
        `${API}/api/web-collection/jobs`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            all_clubs: scope === "all",
            club_ids:
              scope === "all" ? [] : selectedIds,
            start_date: start,
            end_date: end,
            discover_new: discover,
            refresh_existing: refresh,
            collect_followers: followers,
            max_scanned: maxScanned,
            max_details: maxDetails,
            max_new: maxNew,
            max_existing: maxExisting,
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : `Błąd API: HTTP ${response.status}`
        );
      }

      setInfo(
        `Utworzono zadanie #${result.job_id}. ` +
        "Status odświeża się automatycznie."
      );

      const statusResponse = await fetch(
        `${API}/api/web-collection/jobs/${result.job_id}`,
        { cache: "no-store" }
      );

      if (statusResponse.ok) {
        const statusData: { job: Job } =
          await statusResponse.json();

        setJob(statusData.job);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Nie udało się rozpocząć pobierania."
      );
    } finally {
      setStarting(false);
    }
  }

  const visibleClubs = clubs.filter((club) => {
    const query = search.trim().toLowerCase();

    return (
      club.name.toLowerCase().includes(query) ||
      club.handle.toLowerCase().includes(query)
    );
  });

  const running =
    job?.status === "queued" ||
    job?.status === "running";

  const progress =
    job && job.total_clubs > 0
      ? Math.round(
          (job.completed_clubs / job.total_clubs) * 100
        )
      : 0;

  const statusLabel =
    job?.status === "queued"
      ? "W kolejce"
      : job?.status === "running"
        ? "W trakcie"
        : job?.status === "completed"
          ? "Zakończone"
          : job?.status === "partial"
            ? "Zakończone z błędami"
            : job?.status === "failed"
              ? "Błąd zadania"
              : "Brak zadania";

  return (
    <main className="min-h-screen bg-[#090d12] px-5 py-10 text-white">
      <div className="mx-auto max-w-6xl space-y-8">

        <header className="space-y-3">
          <a
            href="/panel/monitoring"
            className="text-sm text-emerald-400 hover:underline"
          >
            ← Collection Monitoring
          </a>

          <p className="text-xs font-semibold tracking-[0.25em] text-emerald-400">
            FOOTBALL SOCIAL INTELLIGENCE
          </p>

          <h1 className="text-3xl font-bold">
            Web Collection Center
          </h1>

          <p className="text-sm text-slate-400">
            Uruchamiaj pobieranie statystyk klubów TikTok
            bezpośrednio ze strony.
          </p>
        </header>

        {/* Wybór klubów */}
        <section className="space-y-5 rounded-xl border border-white/10 bg-[#111923] p-6">
          <h2 className="text-xl font-semibold">
            1. Wybierz kluby
          </h2>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setScope("selected")}
              className={`rounded-lg px-4 py-2 text-sm ${
                scope === "selected"
                  ? "bg-emerald-500 text-black"
                  : "border border-white/10 text-slate-300"
              }`}
            >
              Wybrane kluby
            </button>

            <button
              type="button"
              onClick={() => setScope("all")}
              className={`rounded-lg px-4 py-2 text-sm ${
                scope === "all"
                  ? "bg-emerald-500 text-black"
                  : "border border-white/10 text-slate-300"
              }`}
            >
              Wszystkie aktywne ({clubs.length})
            </button>
          </div>

          {scope === "selected" && (
            <>
              <input
                type="search"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Szukaj klubu..."
                className="w-full rounded-lg border border-white/10 bg-[#090d12] px-4 py-3 text-sm"
              />

              <div className="max-h-64 space-y-2 overflow-y-auto">
                {visibleClubs.map((club) => (
                  <label
                    key={club.id}
                    className="flex cursor-pointer items-center gap-3 rounded-lg border border-white/5 p-3 hover:bg-white/5"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(club.id)}
                      onChange={() => toggleClub(club.id)}
                      className="accent-emerald-500"
                    />

                    <span className="text-sm">
                      {club.name}
                      <span className="ml-2 text-slate-500">
                        @{club.handle}
                      </span>
                    </span>
                  </label>
                ))}
              </div>

              <p className="text-xs text-slate-500">
                Wybrano {selectedIds.length} klubów
              </p>
            </>
          )}

          {scope === "all" && (
            <p className="text-sm text-amber-300">
              Zostaną uwzględnione wszystkie aktywne
              kluby w MySQL. Pobieranie może potrwać długo.
            </p>
          )}

          {loadingClubs && (
            <p className="text-sm text-slate-400">
              Wczytywanie listy klubów...
            </p>
          )}
        </section>

        {/* Zakres dat */}
        <section className="space-y-5 rounded-xl border border-white/10 bg-[#111923] p-6">
          <h2 className="text-xl font-semibold">
            2. Wybierz zakres publikacji
          </h2>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 text-sm text-slate-400">
              <span className="block">Data od</span>
              <input
                type="date"
                value={start}
                onChange={(event) =>
                  setStart(event.target.value)
                }
                className="w-full rounded-lg border border-white/10 bg-[#090d12] px-4 py-3 text-white"
              />
            </label>

            <label className="space-y-2 text-sm text-slate-400">
              <span className="block">Data do</span>
              <input
                type="date"
                value={end}
                onChange={(event) =>
                  setEnd(event.target.value)
                }
                className="w-full rounded-lg border border-white/10 bg-[#090d12] px-4 py-3 text-white"
              />
            </label>
          </div>

          <p className="text-xs text-slate-500">
            Okres dotyczy dat publikacji filmów w UTC.
            Statystyki filmów zostaną pobrane w chwili
            uruchomienia zadania.
          </p>
        </section>

        {/* Rodzaj pobierania */}
        <section className="space-y-5 rounded-xl border border-white/10 bg-[#111923] p-6">
          <h2 className="text-xl font-semibold">
            3. Co chcesz pobrać?
          </h2>

          <div className="space-y-4 text-sm">
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={discover}
                onChange={(event) =>
                  setDiscover(event.target.checked)
                }
                className="mt-1 accent-emerald-500"
              />
              <span>
                <strong>Wykryj nowe filmy</strong>
                <span className="block text-slate-400">
                  Znajdź filmy, których nie ma jeszcze
                  w MySQL, i sprawdź ich daty publikacji.
                </span>
              </span>
            </label>

            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={refresh}
                onChange={(event) =>
                  setRefresh(event.target.checked)
                }
                className="mt-1 accent-emerald-500"
              />
              <span>
                <strong>Odśwież znane filmy</strong>
                <span className="block text-slate-400">
                  Dodaj nowe pomiary statystyk istniejących
                  materiałów z wybranego okresu.
                </span>
              </span>
            </label>

            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={followers}
                onChange={(event) =>
                  setFollowers(event.target.checked)
                }
                className="mt-1 accent-emerald-500"
              />
              <span>
                <strong>Pobierz obserwujących</strong>
                <span className="block text-slate-400">
                  Zapisz aktualną liczbę obserwujących.
                  Tego pomiaru nie dotyczy zakres
                  historycznych dat publikacji filmów.
                </span>
              </span>
            </label>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 text-xs text-slate-400">
              <span className="block">
                Pozycji listy na klub
              </span>
              <select
                value={maxScanned}
                onChange={(e) =>
                  setMaxScanned(Number(e.target.value))
                }
                className="w-full rounded-lg border border-white/10 bg-[#090d12] p-3 text-white"
              >
                <option value={50}>50</option>
                <option value={150}>150</option>
                <option value={250}>250</option>
              </select>
            </label>

            <label className="space-y-2 text-xs text-slate-400">
              <span className="block">
                Maks. szczegółowych prób
              </span>
              <select
                value={maxDetails}
                onChange={(e) =>
                  setMaxDetails(Number(e.target.value))
                }
                className="w-full rounded-lg border border-white/10 bg-[#090d12] p-3 text-white"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={40}>40</option>
                <option value={60}>60</option>
              </select>
            </label>

            <label className="space-y-2 text-xs text-slate-400">
              <span className="block">
                Maks. nowych filmów
              </span>
              <select
                value={maxNew}
                onChange={(e) =>
                  setMaxNew(Number(e.target.value))
                }
                className="w-full rounded-lg border border-white/10 bg-[#090d12] p-3 text-white"
              >
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={10}>10</option>
              </select>
            </label>

            <label className="space-y-2 text-xs text-slate-400">
              <span className="block">
                Maks. odświeżanych filmów
              </span>
              <select
                value={maxExisting}
                onChange={(e) =>
                  setMaxExisting(Number(e.target.value))
                }
                className="w-full rounded-lg border border-white/10 bg-[#090d12] p-3 text-white"
              >
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={10}>10</option>
              </select>
            </label>
          </div>

          <p className="text-xs text-slate-500">
            Limity są stosowane osobno dla każdego
            klubu. Pobieranie nie gwarantuje znalezienia
            wszystkich filmów z okresu.
          </p>
        </section>

        {/* Przycisk uruchomienia */}
        <section className="space-y-4">
          <button
            type="button"
            onClick={startCollection}
            disabled={
              starting ||
              running ||
              loadingClubs ||
              clubs.length === 0 ||
              !start ||
              !end ||
              start > end
            }
            className="w-full rounded-xl bg-emerald-500 px-6 py-4 text-lg font-bold text-black hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {starting
              ? "Uruchamianie zadania..."
              : running
                ? "Trwa pobieranie danych"
                : "Rozpocznij pobieranie danych"}
          </button>

          {info && (
            <p className="text-sm text-emerald-400">
              {info}
            </p>
          )}

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
              {error}
            </div>
          )}
        </section>

        {/* Postęp */}
        <section className="space-y-5 rounded-xl border border-white/10 bg-[#111923] p-6">
          <h2 className="text-xl font-semibold">
            Ostatnie zadanie
          </h2>

          {job === null ? (
            <p className="text-sm text-slate-400">
              Nie uruchomiono jeszcze pobierania
              przez stronę.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold">
                    Zadanie #{job.id}
                  </p>
                  <p className="text-sm text-slate-400">
                    Status: {statusLabel}
                  </p>
                </div>

                <p className="text-2xl font-semibold text-emerald-400">
                  {progress}%
                </p>
              </div>

              <div className="h-3 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-emerald-400 transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>

              <p className="text-sm text-slate-400">
                Kluby: {job.completed_clubs} /{" "}
                {job.total_clubs}
              </p>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Stat
                  label="Nowe filmy"
                  value={job.new_videos}
                />
                <Stat
                  label="Odświeżone filmy"
                  value={job.refreshed_videos}
                />
                <Stat
                  label="Pomiary obserwujących"
                  value={job.followers_saved}
                />
                <Stat
                  label="Błędy"
                  value={job.errors_count}
                />
              </div>

              <p className="text-sm text-slate-300">
                {job.message}
              </p>

              <div className="space-y-1 text-xs text-slate-500">
                <p>
                  Zakres publikacji: {job.start_date} –{" "}
                  {job.end_date}
                </p>
                <p>
                  Rozpoczęto: {formatDate(job.started_at)}
                </p>
                <p>
                  Ostatnia aktywność:{" "}
                  {formatDate(job.heartbeat_at)}
                </p>
                <p>
                  Zakończono: {formatDate(job.finished_at)}
                </p>
              </div>
            </>
          )}
        </section>

        <div className="flex flex-wrap gap-5 text-sm">
          <a
            href="/panel/monitoring"
            className="text-emerald-400 hover:underline"
          >
            Collection Monitoring
          </a>
          <a
            href="/panel/rankingi"
            className="text-emerald-400 hover:underline"
          >
            Rankingi klubów
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
